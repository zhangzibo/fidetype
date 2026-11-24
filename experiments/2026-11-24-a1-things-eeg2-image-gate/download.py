"""Download the A1 inputs (THINGS-EEG2 preprocessed EEG, subjects 1-2, and the image set).

Two file sets:

* ``osf``: the official THINGS-EEG2 files from OSF https://osf.io/3jk45/ (EEG: CC BY 4.0;
  images: research use only, see the image set LICENSE.txt). 17-channel, 100 Hz EEG,
  the image metadata and the image zips.
* ``hf``: the 63-channel, 250 Hz re-preprocessing and the CLIP ViT-H-14 image/text
  features that the ATM authors publish on Hugging Face (dataset
  LidongYang/EEG_Image_decode, CC BY 4.0), pinned to one commit. A1's primary input.

The files go to C:/Users/zhang/bci-data/raw/things-eeg2/<set>/. They are never committed.

The script resumes partial files (curl -C -), retries, and checks the SHA-256 that OSF
publishes. It writes a log and a DONE file. Run it detached:

    python -I download.py --set osf --out C:/Users/zhang/bci-data/raw/things-eeg2
    python -I download.py --set hf  --out C:/Users/zhang/bci-data/raw/things-eeg2
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import time
from pathlib import Path

# name -> (download URL, size in bytes, sha256), from the OSF v2 API on 2026-11-24.
OSF_FILES = {
    "LICENSE.txt": ("https://osf.io/download/3765v/", 3159,
                    "ea94c104d2319aa65d82f4b179531141d3ec1483547826c3a72cfd45015673dc"),
    "image_metadata.npy": ("https://osf.io/download/qkgtf/", 656579,
                           "681a75633c59a356a66ca19a277429c1d48a00a98405ff96e53ee0b9f00b397c"),
    "test_images.zip": ("https://osf.io/download/znu7b/", 8129948,
                        "57ed472cd88f68ccf88e9ecbadf3da91ac222d8548684d5680be95bcf47ec14a"),
    "sub-01.zip": ("https://osf.io/download/nb8wr/", 1071722467,
                   "f25d5ea30ba6811edd7ebd460d7b271edaf527b6920ab2d3d6e7950e9ee9639f"),
    "sub-02.zip": ("https://osf.io/download/u43p5/", 1071516660,
                   "e1eba2d74009c6dd41becf53d84b8d47532103b41110a5855e7e286bcca6fe41"),
    "training_images.zip": ("https://osf.io/download/3v527/", 655039265,
                            "dc9cc627141ba230641f729f84b80eb01f0a963d288c971eefcf76b4a7581f3a"),
}

# Hugging Face dataset LidongYang/EEG_Image_decode at a pinned commit; sha256 = the LFS oid
# from the HF tree API on 2026-11-24.
HF_REV = "dbe34bb2407164f70883c661c76664f0d596e522"
_HF = f"https://huggingface.co/datasets/LidongYang/EEG_Image_decode/resolve/{HF_REV}/"
HF_FILES = {
    "ViT-H-14_features_test.pt": (_HF + "ViT-H-14_features_test.pt", 1639587,
                                  "2d772e733ae9afe01f60547c38f0026a094347aa56fefd77cf375cf53667cdc9"),
    "ViT-H-14_features_train.pt": (_HF + "ViT-H-14_features_train.pt", 74523815,
                                   "b8156300f59d058600fc9a2c9e1586c5fbd4a113f236031acc64c6511d56b432"),
    "sub-01/preprocessed_eeg_test.npy": (
        _HF + "Preprocessed_data_250Hz/sub-01/preprocessed_eeg_test.npy", 2016003002,
        "0489b80781c1a79afa2f952309af30c4a8c1396c5518cdb316b4f3b251a154b9"),
    "sub-02/preprocessed_eeg_test.npy": (
        _HF + "Preprocessed_data_250Hz/sub-02/preprocessed_eeg_test.npy", 2016003002,
        "951ba71502ef10c025e33471f22d9c7944780b997d673400e88e4716043f9408"),
    "sub-01/preprocessed_eeg_training.npy": (
        _HF + "Preprocessed_data_250Hz/sub-01/preprocessed_eeg_training.npy", 8336163007,
        "a6a023c7d8983690aba43f2eaf2e9982739bc0f51981e2e392cb89e014698237"),
    "sub-02/preprocessed_eeg_training.npy": (
        _HF + "Preprocessed_data_250Hz/sub-02/preprocessed_eeg_training.npy", 8336163007,
        "be1becfde2d659d11368f930d1b822c21fc4fb28a19bb95c7f4dc192f5d9b9d0"),
}

SETS = {"osf": OSF_FILES, "hf": HF_FILES}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def log(msg: str, logf: Path) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    with logf.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--set", choices=sorted(SETS), required=True)
    ap.add_argument("--retries", type=int, default=20)
    args = ap.parse_args()
    files = SETS[args.set]
    out = Path(args.out)
    dl = out / args.set
    dl.mkdir(parents=True, exist_ok=True)
    logf = out / f"download_{args.set}.log"
    total = sum(s for _, s, _ in files.values())
    log(f"start {args.set}: {len(files)} files, {total / 1e9:.2f} GB", logf)
    ok = True
    for name, (url, size, digest) in files.items():
        dst = dl / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        done_mark = dl / (name + ".sha256ok")
        if done_mark.exists():
            log(f"skip {name} (verified before)", logf)
            continue
        for attempt in range(1, args.retries + 1):
            have = dst.stat().st_size if dst.exists() else 0
            if have > size:
                dst.unlink()
                have = 0
            if have < size:
                log(f"get {name} attempt {attempt} from byte {have}", logf)
                subprocess.run(
                    ["curl.exe", "-sS", "-L", "--fail", "-C", "-", "--retry", "3",
                     "--speed-limit", "10000", "--speed-time", "120", "-o", str(dst), url],
                    check=False,
                )
            have = dst.stat().st_size if dst.exists() else 0
            if have == size:
                if sha256(dst) == digest:
                    done_mark.write_text(digest, encoding="utf-8")
                    log(f"ok {name} {size} bytes sha256 match", logf)
                    break
                log(f"bad sha256 for {name}; delete and retry", logf)
                dst.unlink()
            time.sleep(min(60, 5 * attempt))
        else:
            log(f"FAILED {name}", logf)
            ok = False
    if ok:
        (out / f"DONE_{args.set}").write_text("ok\n", encoding="utf-8")
        log("all files verified", logf)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
