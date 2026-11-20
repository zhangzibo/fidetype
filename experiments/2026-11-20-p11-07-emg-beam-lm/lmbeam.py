"""P11-07: CTC prefix beam search with shallow character-LM fusion over a key vocabulary with Backspace.

Our own code (Apache-2.0). It reads natural-log CTC frame probabilities over a key vocabulary (the P11-01
98-token vocabulary or the 33-class key-CTC vocabulary of ``fidetype.adapters.emg2qwerty``) and searches key
sequences. The LM scores the *intended text* of a key prefix, not the raw keys:

- a letter key (either case) appends its lower-case letter;
- Space and every other printable non-letter key (digits, ``.``, ``,``, ``'`` ...) append a space, and runs of
  spaces join (the ``normalize_text`` rule that built the Tatoeba LM: non-letters become a space);
- Backspace removes the last intended character: the LM score returns to the score before that character
  (the LM models the intended text; the deleted key costs only its acoustic score);
- Enter starts a new sentence (LM context reset to ``<s>``). Backspace after Enter removes the reset.

Score of a key prefix (rank score of the beam)::

    score = logp_acoustic + w * (logp_LM(intended text) - lam * n_oov_words) + beta * n_keys

``lam`` is the optional word-lexicon term: a word that is closed (by a space-like key, Enter, or the end of the
utterance) and is not in the lexicon costs ``lam``. With ``lam = 0`` no lexicon is used.

Pruning: at each frame only tokens with ``log p >= prune_logp`` extend a prefix (blank and the repeat of the last
token always count). The ``beam`` best prefixes stay. The search is causal: a frame changes only the prefixes
that end at or before it. ``push`` takes frames in chunks; the state carries over (streaming).

The prefix state lives in two trees with parent pointers (no strings in the hot path): key nodes (one per
emitted key, with the frame of emission) and intended-text nodes (LM context of the last ``order - 1``
normalised characters, cumulative LM score, open word).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

NEG_INF = -math.inf

# token kinds
K_BLANK, K_LETTER, K_SPACE, K_PUNCT, K_BS, K_ENTER, K_NONE = range(7)
_BS = {"⌫", "\x08"}
_EN = {"⏎", "\r", "\n"}


def token_table(vocab: list[str], blank: int = 0) -> tuple[np.ndarray, list[str]]:
    """Kind of each token, and its letter (lower case) for letters.

    ``_`` is Space in the 33-class key vocabulary (``key_chars``); in the 98-token vocabulary ``_`` is a
    printable punctuation key. The caller says which by the vocabulary size: a vocabulary with a real ``" "``
    token treats ``_`` as punctuation.
    """
    has_space = " " in vocab
    kinds = np.full(len(vocab), K_NONE, np.int64)
    letters = [""] * len(vocab)
    for i, t in enumerate(vocab):
        if i == blank:
            kinds[i] = K_BLANK
        elif t in _BS:
            kinds[i] = K_BS
        elif t in _EN:
            kinds[i] = K_ENTER
        elif t == " " or (t == "_" and not has_space):
            kinds[i] = K_SPACE
        elif len(t) == 1 and t.isascii() and t.isalpha():
            kinds[i] = K_LETTER
            letters[i] = t.lower()
        elif len(t) == 1 and t.isprintable():
            kinds[i] = K_PUNCT
    return kinds, letters


@dataclass
class Hyp:
    tokens: list[int]
    frames: list[int]
    score: float
    logp_acoustic: float
    logp_lm: float


class LMBeam:
    """Streaming CTC prefix beam search with intended-text LM fusion (see the module docstring)."""

    def __init__(self, vocab: list[str], blank: int = 0, lm=None, lm_weight: float = 0.0, bonus: float = 0.0,
                 beam: int = 16, prune_logp: float = -8.0, lexicon: frozenset[str] | None = None,
                 lam: float = 0.0) -> None:
        self.vocab = list(vocab)
        self.V = V = len(vocab)
        self.blank = blank
        self.kinds, self.letters = token_table(self.vocab, blank)
        self.lm = lm
        self.w = float(lm_weight) if lm is not None else 0.0
        self.bonus = float(bonus)
        self.B = int(beam)
        self.prune = float(prune_logp)
        self.lex = lexicon if (lexicon is not None and lam > 0) else None
        self.lam = float(lam) if self.lex is not None else 0.0
        self.order1 = (lm.order - 1) if lm is not None else 0
        # LM column of each letter token in logprobs_vocab (1..26), space = 27
        self._let_col = np.array([(ord(self.letters[i]) - 96) if self.kinds[i] == K_LETTER else 0 for i in range(V)])
        self._is_let = self.kinds == K_LETTER
        self._is_sp = (self.kinds == K_SPACE) | (self.kinds == K_PUNCT)
        self._is_bs = self.kinds == K_BS
        self._is_en = self.kinds == K_ENTER
        self._allowed = (self.kinds != K_BLANK) & (self.kinds != K_NONE)
        self._row_cache: dict[tuple[str, int], np.ndarray] = {}
        # intended nodes: parent, cumulative LM, context, open word
        self.i_par: list[int] = [-1]
        self.i_cum: list[float] = [0.0]
        self.i_ctx: list[str] = [""]
        self.i_word: list[str] = [""]
        # key nodes: parent, token, frame, intended node
        self.k_par: list[int] = [-1]
        self.k_tok: list[int] = [-1]
        self.k_fr: list[int] = [-1]
        self.k_in: list[int] = [0]
        # beam state
        self.nodes = np.array([0], np.int64)
        self.par = np.array([-1], np.int64)
        self.last = np.array([-1], np.int64)
        self.pb = np.array([0.0])
        self.pnb = np.array([NEG_INF])
        self.lms = np.array([0.0])
        self.ln = np.array([0.0])
        self.L = self._row(0)[None, :].copy()
        self.t = 0

    # --- LM rows ---------------------------------------------------------------------------------------

    def _wstate(self, word: str) -> int:
        if not word or self.lex is None:
            return 0
        return 1 if word in self.lex else 2

    def _close(self, word: str) -> float:
        """LM-side cost of closing ``word`` (lexicon term)."""
        return -self.lam if (word and self.lex is not None and word not in self.lex) else 0.0

    def _row(self, n: int) -> np.ndarray:
        """LM delta of each token from intended node ``n`` (unweighted)."""
        ctx, word = self.i_ctx[n], self.i_word[n]
        key = (ctx, self._wstate(word))
        base = self._row_cache.get(key)
        if base is None:
            base = np.zeros(self.V)
            if self.lm is not None:
                lp = np.asarray(self.lm.logprobs_vocab(ctx), np.float64)
                base[self._is_let] = lp[self._let_col[self._is_let]]
                collapse = ctx == "" or ctx.endswith(" ")
                base[self._is_sp] = 0.0 if collapse else lp[27] + self._close(word)
            else:
                base[self._is_sp] = self._close(word)
            base[self._is_en] = self._close(word)
            if len(self._row_cache) > 400_000:
                self._row_cache.clear()
            self._row_cache[key] = base
        if self._is_bs.any():
            p = self.i_par[n]
            r = base.copy()
            r[self._is_bs] = (self.i_cum[p] - self.i_cum[n]) if p >= 0 else 0.0
            return r
        return base

    def _push_intended(self, n: int, tok: int) -> int:
        k = self.kinds[tok]
        if k == K_BS:
            p = self.i_par[n]
            return p if p >= 0 else n
        ctx, word, cum = self.i_ctx[n], self.i_word[n], self.i_cum[n]
        if k == K_ENTER:
            nctx, nword, d = "", "", self._close(word)
        elif k == K_LETTER:
            ch = self.letters[tok]
            d = float(self.lm.logprobs_vocab(ctx)[ord(ch) - 96]) if self.lm is not None else 0.0
            nctx = (ctx + ch)[-self.order1:] if self.order1 else ""
            nword = (word + ch)[-40:]
        else:  # space-like: Space and the other printable non-letter keys
            collapse = (ctx == "" or ctx.endswith(" ")) if self.lm is not None else word == ""
            if collapse:
                d, nctx = 0.0, ctx
            else:
                d = (float(self.lm.logprobs_vocab(ctx)[27]) if self.lm is not None else 0.0) + self._close(word)
                nctx = (ctx + " ")[-self.order1:] if self.order1 else ""
            nword = ""
        self.i_par.append(n)
        self.i_cum.append(cum + d)
        self.i_ctx.append(nctx)
        self.i_word.append(nword)
        return len(self.i_par) - 1

    # --- search ----------------------------------------------------------------------------------------

    def push(self, log_probs: np.ndarray) -> None:
        lp = np.asarray(log_probs, np.float64)
        if lp.ndim != 2 or lp.shape[1] != self.V:
            raise ValueError(f"chunk must be (n, {self.V}), got {lp.shape}")
        allow = (lp >= self.prune) & self._allowed[None, :]
        active = allow.any(axis=1)
        blank, w, bonus, B = self.blank, self.w, self.bonus, self.B
        nodes, par, last, pb, pnb, lms, ln, L = (self.nodes, self.par, self.last, self.pb, self.pnb, self.lms,
                                                 self.ln, self.L)
        for t in range(lp.shape[0]):
            row = lp[t]
            ptot = np.logaddexp(pb, pnb)
            s_pb = ptot + row[blank]
            s_pnb = np.where(last >= 0, pnb + row[np.maximum(last, 0)], NEG_INF)
            if not active[t]:
                pb, pnb = s_pb, s_pnb
                continue
            C = np.nonzero(allow[t])[0]
            # acoustic score of each extension (b, c)
            same = last[:, None] == C[None, :]
            ext = np.where(same, pb[:, None], ptot[:, None]) + row[C][None, :]
            # merge: an extension that gives a prefix already in the beam joins that prefix
            if len(nodes) > 1:
                order = np.argsort(nodes, kind="stable")
                sn = nodes[order]
                pos = np.searchsorted(sn, par)
                pos = np.minimum(pos, len(sn) - 1)
                hit = (sn[pos] == par) & (par >= 0)
                if hit.any():
                    j = np.nonzero(hit)[0]
                    b = order[pos[j]]
                    cpos = np.searchsorted(C, last[j])
                    cpos = np.minimum(cpos, len(C) - 1)
                    okc = C[cpos] == last[j]
                    if okc.any():
                        j, b, cpos = j[okc], b[okc], cpos[okc]
                        s_pnb[j] = np.logaddexp(s_pnb[j], ext[b, cpos])
                        ext[b, cpos] = NEG_INF
            stay = np.logaddexp(s_pb, s_pnb) + w * lms + bonus * ln
            flat = (ext + w * (lms[:, None] + L[:, C]) + bonus * (ln[:, None] + 1.0)).ravel()
            ok = np.nonzero(flat > NEG_INF)[0]
            if ok.size > B:
                ok = ok[np.argpartition(-flat[ok], B - 1)[:B]]
            ss = np.nonzero(stay > NEG_INF)[0]
            scores = np.concatenate([stay[ss], flat[ok]])
            kind = np.concatenate([np.zeros(ss.size, np.int64), np.ones(ok.size, np.int64)])
            idx = np.concatenate([ss, ok])
            rank = np.lexsort((idx, kind, -scores))[:B]
            isx = kind[rank] == 1
            src = idx[rank]
            K = len(C)
            pb_i = np.where(isx, src // K, src)
            ci = np.where(isx, src % K, 0)
            tok = np.where(isx, C[ci], -1)
            n_pb = np.where(isx, NEG_INF, s_pb[pb_i])
            n_pnb = np.where(isx, ext[pb_i, ci], s_pnb[pb_i])
            n_nodes = nodes[pb_i].copy()
            n_par = par[pb_i].copy()
            n_last = last[pb_i].copy()
            n_lms = lms[pb_i].copy()
            n_ln = ln[pb_i] + isx
            n_L = L[pb_i].copy()
            for q in np.nonzero(isx)[0].tolist():
                parent = int(nodes[pb_i[q]])
                tk = int(tok[q])
                inode = self._push_intended(self.k_in[parent], tk)
                self.k_par.append(parent)
                self.k_tok.append(tk)
                self.k_fr.append(self.t + t)
                self.k_in.append(inode)
                nid = len(self.k_par) - 1
                n_nodes[q] = nid
                n_par[q] = parent
                n_last[q] = tk
                n_lms[q] = self.i_cum[inode]
                n_L[q] = self._row(inode)
            nodes, par, last, pb, pnb, lms, ln, L = n_nodes, n_par, n_last, n_pb, n_pnb, n_lms, n_ln, n_L
        self.nodes, self.par, self.last, self.pb, self.pnb, self.lms, self.ln, self.L = (nodes, par, last, pb, pnb,
                                                                                         lms, ln, L)
        self.t += lp.shape[0]

    # --- results ---------------------------------------------------------------------------------------

    def _end_lm(self, inode: int, eos: bool) -> float:
        word = self.i_word[inode]
        e = self._close(word)
        if eos and self.lm is not None:
            ctx = self.i_ctx[inode]
            e += float(self.lm.logprobs_vocab(ctx.rstrip(" ") if ctx.endswith(" ") else ctx)[0])
        return e

    def path(self, node: int) -> tuple[list[int], list[int]]:
        toks, frs = [], []
        while node > 0:
            toks.append(self.k_tok[node])
            frs.append(self.k_fr[node])
            node = self.k_par[node]
        return toks[::-1], frs[::-1]

    def nbest(self, n: int | None = None, eos: bool = True) -> list[Hyp]:
        """Final hypotheses, best first, with the end terms (open word, ``</s>``)."""
        out = []
        for j in range(len(self.nodes)):
            node = int(self.nodes[j])
            ac = float(np.logaddexp(self.pb[j], self.pnb[j]))
            if ac == NEG_INF:
                continue
            lml = float(self.lms[j]) + self._end_lm(self.k_in[node], eos)
            sc = ac + self.w * lml + self.bonus * float(self.ln[j])
            out.append((sc, j, node, ac, lml))
        out.sort(key=lambda x: (-x[0], x[1]))
        if n is not None:
            out = out[:n]
        res = []
        for sc, _, node, ac, lml in out:
            toks, frs = self.path(node)
            res.append(Hyp(toks, frs, sc, ac, lml))
        return res


def greedy_tokens(lp: np.ndarray, blank: int = 0) -> list[int]:
    a = np.asarray(lp).argmax(1)
    if len(a) == 0:
        return []
    keep = np.concatenate([[True], a[1:] != a[:-1]])
    a = a[keep]
    return [int(x) for x in a[a != blank]]
