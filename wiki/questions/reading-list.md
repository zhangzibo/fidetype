---
title: "Reading list: trustworthy neural text entry"
type: question
tags: [reading-list, calibration, conformal-prediction, selective-prediction, hallucination, streaming, text-entry, bci]
sources: []
updated: 2026-11-07
---

# Reading list: trustworthy neural text entry

This page lists papers for the project "trustworthy neural text entry". The project builds a decoder-agnostic layer. The layer takes text from any neural decoder (MEG, EEG, wrist EMG, intracortical). It calibrates confidence, outputs conformal prediction sets, abstains or offers n-best choices, and guards against LLM hallucination. It decodes causally, in real time. See [architecture](architecture.md) for the design and [direction decision](direction-decision.md) for the reasons.

The first paper is "calibrated, abstaining brain-to-text" on SpanishBCBL ([Brain2Qwerty v1](../sources/brain2qwerty-v1.md)). It reports "effective words per minute" (eWPM) with a simulated user who picks from an n-best list.

**Verification.** We checked every entry on 2026-11-07. We opened its arXiv record, DOI record (Crossref), publisher page or proceedings page. We confirmed the title, the authors and the year. For arXiv-only entries, the year is the first arXiv version. A venue in the list is the publication venue when we know it; otherwise the list says "arXiv".

**Priority tags.** [must] = read before the first paper. [should] = read during the first paper. [optional] = read when the topic comes up.

## Start here (reading order)

1. **Noninvasive decoding of typed sentences from human brain activity** (Lévy et al., 2026). It defines the SpanishBCBL task and the baseline that we wrap. See [v1](../sources/brain2qwerty-v1.md).
2. **Accurate Decoding of Natural Sentences from Non-Invasive Brain Recordings** (Zhang, Lévy et al., 2026). It shows the CTC + LLM pipeline and the place where an LLM can hallucinate. See [v2](../sources/brain2qwerty-v2.md).
3. **On Calibration of Modern Neural Networks** (Guo et al., 2017). It defines ECE and temperature scaling, our first calibration baseline.
4. **A Gentle Introduction to Conformal Prediction** (Angelopoulos & Bates, 2021). It gives the split-conformal recipe for our prediction sets.
5. **Prototyping Co-Control Brain–Computer Interfaces Through Brain-to-Text** (Huang et al., 2025). It shows that better calibration and better alternatives improve brain-to-text fusion. This is our closest prior work.
6. **Selective Classification for Deep Neural Networks** (Geifman & El-Yaniv, 2017). It defines the risk–coverage trade-off that our abstention reports.
7. **Detecting hallucinations in large language models using semantic entropy** (Farquhar et al., 2024). It gives a strong method to flag fluent but wrong LLM output.
8. **Using large language models to accelerate communication for eye gaze typing users with ALS** (Cai et al., 2024). It measures real gains when a user picks from LLM suggestions. This is the model for our eWPM simulation.

---

## 1. Brain-to-text foundations

- [must] **Noninvasive decoding of typed sentences from human brain activity**. Lévy, Zhang, Pinet et al. *Nature Neuroscience*, 2026. https://doi.org/10.1038/s41593-026-02303-2
  Brain2Qwerty v1. It supplies the SpanishBCBL dataset and our baseline decoder ([v1](../sources/brain2qwerty-v1.md)).
- [must] **Accurate Decoding of Natural Sentences from Non-Invasive Brain Recordings**. Zhang, Lévy et al. Meta preprint, 2026. https://facebookresearch.github.io/brain2qwerty/assets/brain2qwerty_v2.pdf
  Brain2Qwerty v2. Its LLM stage is the main hallucination risk that our layer must catch ([v2](../sources/brain2qwerty-v2.md)).
- [must] **High-performance brain-to-text communication via handwriting**. Willett et al. *Nature*, 2021. https://doi.org/10.1038/s41586-021-03506-2
  It is the reference intracortical typing BCI. It uses an RNN decoder and a language model.
- [must] **A high-performance speech neuroprosthesis**. Willett et al. *Nature*, 2023. https://doi.org/10.1038/s41586-023-06377-x
  It sets the phoneme-CTC + n-gram + LLM pipeline that most brain-to-text work copies.
- [should] **An Accurate and Rapidly Calibrating Speech Neuroprosthesis**. Card et al. *NEJM*, 2024. https://doi.org/10.1056/NEJMoa2314132
  It shows daily use with high accuracy. Its data is the Brain-to-Text '25 benchmark.
- [should] **A high-performance neuroprosthesis for speech decoding and avatar control**. Metzger et al. *Nature*, 2023. https://doi.org/10.1038/s41586-023-06443-4
  It decodes text, speech and avatar output from ECoG. It is a second decoder family for our layer.
- [should] **Restoring rapid natural bimanual typing with a neuroprosthesis after paralysis**. Jude et al. *Nature Neuroscience*, 2026. https://doi.org/10.1038/s41593-026-02218-y
  It decodes attempted QWERTY typing from motor cortex. It is the intracortical twin of the Brain2Qwerty task.
- [should] **Brain-to-Text Benchmark '24: Lessons Learned**. Willett et al. arXiv, 2024. https://arxiv.org/abs/2412.17227
  It summarises the winning methods (ensembles, LLM rescoring). These are the decoders our layer must wrap.
- [should] **Decoding speech perception from non-invasive brain recordings**. Défossez et al. *Nature Machine Intelligence*, 2023. https://doi.org/10.1038/s42256-023-00714-5
  It is Meta's MEG/EEG contrastive decoding work. Brain2Qwerty builds on it.
- [should] **Semantic reconstruction of continuous language from non-invasive brain recordings**. Tang et al. *Nature Neuroscience*, 2023. https://doi.org/10.1038/s41593-023-01304-9
  It decodes meaning from fMRI with an LLM prior. It shows how fluent output can hide wrong content.
- [optional] **A cross-species neural foundation model for end-to-end speech decoding**. Zhang, He, Fan et al. ICLR 2026 (arXiv 2025). https://arxiv.org/abs/2511.21740
  It reports state-of-the-art results on Brain-to-Text '24 and '25. Its appendix describes the '25 leaderboard setup.
- [optional] **BrainWhisperer: Leveraging Large-Scale ASR Models for Neural Speech Decoding**. Boccato et al. arXiv, 2026. https://arxiv.org/abs/2603.13321
  It placed 4th in Brain-to-Text '25. It shows how ASR models transfer to neural decoding.
- [optional] **Unlocking Non-Invasive Brain-to-Text**. Jayalath, Landau, Parker Jones. arXiv, 2025. https://arxiv.org/abs/2505.13446
  It is a non-invasive brain-to-text baseline from the LibriBrain group, with LLM rescoring.
- [optional] **A streaming brain-to-voice neuroprosthesis to restore naturalistic communication**. Littlejohn et al. *Nature Neuroscience*, 2025. https://doi.org/10.1038/s41593-025-01905-6
  It decodes causally in small steps. It is a model for our real-time constraint.
- [optional] **An instantaneous voice-synthesis neuroprosthesis**. Wairagkar et al. *Nature*, 2025. https://doi.org/10.1038/s41586-025-09127-3
  It shows very low-latency causal decoding from intracortical arrays.
- [optional] **Neuroprosthesis for Decoding Speech in a Paralyzed Person with Anarthria**. Moses et al. *NEJM*, 2021. https://doi.org/10.1056/NEJMoa2027540
  It is the first word-level speech BCI. It uses a language model with a small vocabulary.

## 2. Calibration and uncertainty in neural decoding and BCI

- [must] **Prototyping Co-Control Brain–Computer Interfaces Through Brain-to-Text**. Huang, Narasimha, Patel, Mishne, Gilja. NeurIPS 2025 Workshop "Data on the Brain and Mind". https://neurips.cc/virtual/2025/131375
  It changes the decoder's output distribution but keeps the same top choice. Better calibration and alternatives improve the result. This directly supports our thesis.
- [must] **Confidence-Aware Neural Decoding of Overt Speech from EEG: Toward Robust Brain-Computer Interfaces**. Kim, Ko, Lee. arXiv, 2025. https://arxiv.org/abs/2511.07890
  It combines deep ensembles, post-hoc calibration and abstention for EEG speech. It is a near baseline for our first paper.
- [should] **Errare machinale est: the use of error-related potentials in brain-machine interfaces**. Chavarriaga, Sobolewski, Millán. *Frontiers in Neuroscience*, 2014. https://doi.org/10.3389/fnins.2014.00208
  It reviews brain signals that mark errors. They are a possible extra confidence input.
- [should] **A Cross-Modal Approach to Silent Speech with LLM-Enhanced Recognition**. Benster et al. arXiv, 2024. https://arxiv.org/abs/2403.05583
  It uses an LLM to merge n-best lists from several decoders. This is the same place where our guard sits.
- [optional] **Uncertainty Detection and Reduction in Neural Decoding of EEG Signals**. Duan et al. arXiv, 2021. https://arxiv.org/abs/2201.00627
  It estimates EEG decoder uncertainty with dropout and Bayesian networks.
- [optional] **Robust Motor Imagery Tasks Classification Approach Using Bayesian Neural Network**. Milanés-Hermosilla et al. *Sensors*, 2023. https://doi.org/10.3390/s23020703
  It uses a reject option with an adaptive threshold in an EEG BCI.
- [optional] **Generalizable spelling using a speech neuroprosthesis in an individual with severe limb and vocal paralysis**. Metzger et al. *Nature Communications*, 2022. https://doi.org/10.1038/s41467-022-33611-3
  It is a spelling BCI with beam search and a language model. It shows how the LM corrects letter errors.

## 3. Calibration of deep networks and sequence models

- [must] **On Calibration of Modern Neural Networks**. Guo et al. ICML, 2017. https://arxiv.org/abs/1706.04599
  It defines ECE and temperature scaling. We use both from day one.
- [should] **Calibration of Encoder Decoder Models for Neural Machine Translation**. Kumar & Sarawagi. arXiv, 2019. https://arxiv.org/abs/1903.00802
  It shows that seq2seq models are miscalibrated per token and at the end of a sequence.
- [should] **Confidence Estimation for Attention-based Sequence-to-sequence Models for Speech Recognition**. Li et al. ICASSP, 2021. https://arxiv.org/abs/2010.11428
  It trains a small confidence model on top of an ASR decoder. We can copy this for word-level confidence.
- [should] **An evaluation of word-level confidence estimation for end-to-end automatic speech recognition**. Oneata et al. arXiv, 2021. https://arxiv.org/abs/2101.05525
  It compares word-confidence methods, including temperature scaling and dropout, on end-to-end ASR.
- [should] **Fast Entropy-Based Methods of Word-Level Confidence Estimation for End-To-End Automatic Speech Recognition**. Laptev & Ginsburg. arXiv, 2022. https://arxiv.org/abs/2212.08703
  It gives cheap entropy-based word confidence for CTC and RNN-T. It fits a real-time layer.
- [should] **Confidence measures for speech recognition: A survey**. Jiang. *Speech Communication*, 2005. https://doi.org/10.1016/j.specom.2004.12.004
  It is the classic survey of ASR confidence measures.
- [should] **Can You Trust Your Model's Uncertainty? Evaluating Predictive Uncertainty Under Dataset Shift**. Ovadia et al. NeurIPS, 2019. https://arxiv.org/abs/1906.02530
  It shows that calibration breaks under shift. Cross-session neural data has this shift.
- [should] **Simple and Scalable Predictive Uncertainty Estimation using Deep Ensembles**. Lakshminarayanan et al. NeurIPS, 2017. https://arxiv.org/abs/1612.01474
  It is the ensemble baseline. Brain2Qwerty v2 model soups are a related idea.
- [optional] **Identifying and Calibrating Overconfidence in Noisy Speech Recognition**. Huo, Zhang, Tang. arXiv, 2025. https://arxiv.org/abs/2509.07195
  It applies temperature scaling only to overconfident tokens. Noisy speech is like noisy neural data.
- [optional] **Context-Aware Selective Label Smoothing for Calibrating Sequence Recognition Model**. Huang et al. arXiv, 2023. https://arxiv.org/abs/2303.06946
  It calibrates sequence recognisers during training. It compares with temperature scaling.
- [optional] **Language Models (Mostly) Know What They Know**. Kadavath et al. arXiv, 2022. https://arxiv.org/abs/2207.05221
  It tests LLM self-confidence. This matters when the LLM stage rates its own corrections.

## 4. Conformal prediction

- [must] **A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification**. Angelopoulos & Bates. arXiv, 2021. https://arxiv.org/abs/2107.07511
  It is the practical guide. We follow its split-conformal recipe.
- [must] **Adaptive Conformal Inference Under Distribution Shift**. Gibbs & Candès. NeurIPS, 2021. https://arxiv.org/abs/2106.00170
  It keeps coverage when data drift over time. Neural signals drift within and across sessions.
- [must] **Conformal Language Modeling**. Quach et al. ICLR, 2024 (arXiv 2023). https://arxiv.org/abs/2306.10193
  It builds sets of sampled sentences with a coverage guarantee. This maps directly to n-best sets.
- [must] **Applying the conformal prediction paradigm for the uncertainty quantification of an end-to-end automatic speech recognition model (wav2vec 2.0)**. Ernez et al. COPA 2023, PMLR 204. https://proceedings.mlr.press/v204/ernez23a.html
  It builds conformal sets of ASR transcripts with WER control and flags uncertain words. It is the closest ASR template.
- [should] **Conformal Risk Control**. Angelopoulos et al. ICLR, 2024 (arXiv 2022). https://arxiv.org/abs/2208.02814
  It controls expected loss, such as WER, not only miscoverage.
- [should] **Confident and Adaptive Generative Speech Recognition via Risk Control**. Damri & Laufer-Goldshtein. ICLR, 2026. https://openreview.net/forum?id=ck5T7QeiDh
  It decides when to trust LLM error correction of ASR, with a risk guarantee. This matches our hallucination guard.
- [should] **Uncertainty Sets for Image Classifiers using Conformal Prediction**. Angelopoulos et al. ICLR, 2021. https://arxiv.org/abs/2009.14193
  It introduces RAPS, which gives small and stable sets. Small sets matter for the user.
- [should] **Classification with Valid and Adaptive Coverage**. Romano, Sesia, Candès. NeurIPS, 2020. https://arxiv.org/abs/2006.02544
  It introduces APS, the adaptive set score that RAPS builds on.
- [should] **Improving Expert Predictions with Conformal Prediction**. Straitouri et al. ICML, 2023. https://arxiv.org/abs/2201.12006
  It shows that a human who picks from a conformal set does better. This supports our eWPM user model.
- [should] **Language Models with Conformal Factuality Guarantees**. Mohri & Hashimoto. ICML, 2024. https://arxiv.org/abs/2402.10978
  It removes uncertain claims from LLM output with a guarantee.
- [optional] **Conformal Inference for Online Prediction with Arbitrary Distribution Shifts**. Gibbs & Candès. arXiv, 2022. https://arxiv.org/abs/2208.08401
  It extends ACI with automatic step-size tuning.
- [optional] **Conformal PID Control for Time Series Prediction**. Angelopoulos, Candès, Tibshirani. NeurIPS, 2023. https://arxiv.org/abs/2307.16895
  It is a stronger online method for streaming coverage.
- [optional] **Adaptive Conformal Predictions for Time Series**. Zaffran et al. ICML, 2022. https://arxiv.org/abs/2202.07282
  It aggregates several ACI step sizes (AgACI).
- [optional] **Conformal prediction beyond exchangeability**. Barber et al. arXiv, 2022. https://arxiv.org/abs/2202.13415
  It gives theory for weighted conformal prediction when exchangeability fails.
- [optional] **Conformal Prediction with Large Language Models for Multi-Choice Question Answering**. Kumar et al. arXiv, 2023. https://arxiv.org/abs/2305.18404
  It applies conformal sets to LLM answer choices.
- [optional] **On the Utility of Prediction Sets in Human-AI Teams**. Babbar, Bhatt, Weller. IJCAI, 2022. https://arxiv.org/abs/2205.01411
  It runs user studies on how set size changes human accuracy.

## 5. Selective prediction and abstention

- [must] **Selective Classification for Deep Neural Networks**. Geifman & El-Yaniv. NeurIPS, 2017. https://arxiv.org/abs/1705.08500
  It gives risk–coverage curves with a guarantee. We report them for abstention.
- [should] **SelectiveNet: A Deep Neural Network with an Integrated Reject Option**. Geifman & El-Yaniv. ICML, 2019. https://arxiv.org/abs/1901.09192
  It trains the reject option jointly with the model.
- [should] **On optimum recognition error and reject tradeoff**. Chow. *IEEE Transactions on Information Theory*, 1970. https://doi.org/10.1109/TIT.1970.1054406
  It is the original error–reject theory.
- [should] **A Baseline for Detecting Misclassified and Out-of-Distribution Examples in Neural Networks**. Hendrycks & Gimpel. ICLR, 2017. https://arxiv.org/abs/1610.02136
  It gives the max-softmax baseline that every abstention method must beat.
- [should] **Know Your Limits: A Survey of Abstention in Large Language Models**. Wen et al. arXiv, 2024. https://arxiv.org/abs/2407.18418
  It maps the methods for LLM abstention.
- [should] **Mitigating LLM Hallucinations via Conformal Abstention**. Abbasi Yadkori et al. arXiv, 2024. https://arxiv.org/abs/2405.01563
  It decides when an LLM must abstain, with a conformal guarantee. It joins topics 4, 5 and 6.
- [optional] **Selective Question Answering under Domain Shift**. Kamath, Jia, Liang. ACL, 2020. https://arxiv.org/abs/2006.09462
  It trains a calibrator for abstention under shift.
- [optional] **Don't Hallucinate, Abstain: Identifying LLM Knowledge Gaps via Multi-LLM Collaboration**. Feng et al. ACL, 2024. https://arxiv.org/abs/2402.00367
  It compares many LLM abstention methods.

## 6. LLM hallucination detection

- [must] **Detecting hallucinations in large language models using semantic entropy**. Farquhar et al. *Nature*, 2024. https://doi.org/10.1038/s41586-024-07421-0
  It clusters samples by meaning and measures entropy over the clusters. Many sentence candidates with different meanings signal risk.
- [should] **Semantic Uncertainty: Linguistic Invariances for Uncertainty Estimation in Natural Language Generation**. Kuhn, Gal, Farquhar. ICLR, 2023. https://arxiv.org/abs/2302.09664
  It is the first semantic-entropy paper.
- [should] **Semantic Entropy Probes: Robust and Cheap Hallucination Detection in LLMs**. Kossen et al. arXiv, 2024. https://arxiv.org/abs/2406.15927
  It predicts semantic entropy from hidden states in one pass. This fits real time.
- [should] **SelfCheckGPT: Zero-Resource Black-Box Hallucination Detection for Generative Large Language Models**. Manakul, Liusie, Gales. EMNLP, 2023. https://arxiv.org/abs/2303.08896
  It checks agreement between samples. It needs no access to model internals.
- [should] **Trusting Your Evidence: Hallucinate Less with Context-aware Decoding**. Shi et al. NAACL, 2024. https://arxiv.org/abs/2305.14739
  It contrasts output with and without the evidence. For us, the evidence is the neural decoder's output.
- [should] **Careless Whisper: Speech-to-Text Hallucination Harms**. Koenecke et al. FAccT, 2024. https://arxiv.org/abs/2402.08021
  It documents harmful hallucinations in a real speech-to-text system. It motivates our guard.
- [should] **HyPoradise: An Open Baseline for Generative Speech Recognition with Large Language Models**. Chen et al. NeurIPS, 2023. https://arxiv.org/abs/2309.15701
  It gives n-best-to-text LLM correction for ASR. Brain2Qwerty v2 uses the same pattern.
- [optional] **DoLa: Decoding by Contrasting Layers Improves Factuality in Large Language Models**. Chuang et al. ICLR, 2024. https://arxiv.org/abs/2309.03883
  It contrasts early and late layers to reduce the effect of a strong prior.
- [optional] **Lookback Lens: Detecting and Mitigating Contextual Hallucinations in Large Language Models Using Only Attention Maps**. Chuang et al. EMNLP, 2024. https://arxiv.org/abs/2407.07071
  It measures how much the LLM attends to its input. Low attention to the neural evidence is a warning sign.
- [optional] **Survey of Hallucination in Natural Language Generation**. Ji et al. *ACM Computing Surveys*, 2023 (arXiv 2022). https://arxiv.org/abs/2202.03629
  It defines the types of hallucination.

## 7. Streaming and causal sequence decoding

- [must] **Connectionist temporal classification: labelling unsegmented sequence data with recurrent neural networks**. Graves et al. ICML, 2006. https://doi.org/10.1145/1143844.1143891
  It defines CTC. Brain2Qwerty v2 and emg2qwerty both use it ([CTC](../concepts/ctc.md)).
- [must] **emg2qwerty: A Large Dataset with Baselines for Touch Typing using Surface Electromyography**. Sivakumar et al. NeurIPS Datasets and Benchmarks, 2024. https://arxiv.org/abs/2410.20081
  It is a causal CTC typing decoder with a public dataset. It is our second test modality.
- [should] **Conformer: Convolution-augmented Transformer for Speech Recognition**. Gulati et al. Interspeech, 2020. https://arxiv.org/abs/2005.08100
  It is the encoder in Brain2Qwerty v2.
- [should] **Sequence Transduction with Recurrent Neural Networks**. Graves. arXiv, 2012. https://arxiv.org/abs/1211.3711
  It defines RNN-T, the standard streaming ASR loss.
- [should] **Streaming End-to-end Speech Recognition For Mobile Devices**. He et al. ICASSP, 2019. https://arxiv.org/abs/1811.06621
  It shows a production streaming RNN-T on a phone.
- [should] **Emformer: Efficient Memory Transformer Based Acoustic Model For Low Latency Streaming Speech Recognition**. Shi et al. ICASSP, 2021. https://arxiv.org/abs/2010.10759
  It gives a streaming transformer with memory and limited lookahead.
- [should] **Stateful Conformer with Cache-based Inference for Streaming Automatic Speech Recognition**. Noroozi et al. ICASSP, 2024. https://arxiv.org/abs/2312.17279
  It makes a Conformer causal with caches. This is a direct route to a causal Brain2Qwerty encoder.
- [should] **Deep Speech: Scaling up end-to-end speech recognition**. Hannun et al. arXiv, 2014. https://arxiv.org/abs/1412.5567
  It gives CTC prefix beam search with n-gram shallow fusion. This step produces our n-best lists.
- [should] **An analysis of incorporating an external language model into a sequence-to-sequence model**. Kannan et al. ICASSP, 2018. https://arxiv.org/abs/1712.01996
  It analyses shallow fusion weights.
- [optional] **On Using Monolingual Corpora in Neural Machine Translation**. Gulcehre et al. arXiv, 2015. https://arxiv.org/abs/1503.03535
  It introduces shallow and deep fusion.
- [optional] **Hybrid CTC/Attention Architecture for End-to-End Speech Recognition**. Watanabe et al. *IEEE JSTSP*, 2017. https://doi.org/10.1109/JSTSP.2017.2763455
  It joins CTC and attention scores in one beam search.
- [optional] **Unified Streaming and Non-streaming Two-pass End-to-end Model for Speech Recognition**. Zhang et al. arXiv, 2020. https://arxiv.org/abs/2012.05481
  It trains one model for streaming and full context with dynamic chunks (WeNet U2).
- [optional] **LightBeam: An Accurate and Memory-Efficient CTC Decoder for Speech Neuroprostheses**. Feghhi et al. arXiv, 2026. https://arxiv.org/abs/2603.14002
  It fuses an LLM into CTC beam search for speech BCIs, with delayed fusion.

## 8. Text entry, AAC and communication-rate metrics

- [must] **Using large language models to accelerate communication for eye gaze typing users with ALS**. Cai et al. *Nature Communications*, 2024. https://doi.org/10.1038/s41467-024-53873-3
  SpeakFaster. Users pick from LLM suggestions and save keystrokes. It is the model for eWPM.
- [must] **The Utility Metric: A Novel Method to Assess the Overall Performance of Discrete Brain–Computer Interfaces**. Dal Seno, Matteucci, Mainardi. *IEEE TNSRE*, 2010. https://doi.org/10.1109/TNSRE.2009.2032642
  It counts the cost of error correction. eWPM must do the same.
- [should] **Brain–computer interfaces for communication and control**. Wolpaw et al. *Clinical Neurophysiology*, 2002. https://doi.org/10.1016/S1388-2457(02)00057-3
  It is the standard source for the ITR formula.
- [should] **EEG-based communication: improved accuracy by response verification**. Wolpaw et al. *IEEE Transactions on Rehabilitation Engineering*, 1998. https://doi.org/10.1109/86.712231
  It introduces the bit-rate measure and shows the value of verifying a selection.
- [should] **A study of the existing problems of estimating the information transfer rate in online brain–computer interfaces**. Yuan et al. *Journal of Neural Engineering*, 2013. https://doi.org/10.1088/1741-2560/10/2/026014
  It lists where ITR misleads. We cite it to justify eWPM.
- [should] **Performance assessment in brain-computer interface-based augmentative and alternative communication**. Thompson, Blain-Moraes, Huggins. *BioMedical Engineering OnLine*, 2013. https://doi.org/10.1186/1475-925X-12-43
  It reviews BCI-AAC metrics and asks for user-centred measures.
- [should] **Metrics for text entry research: an evaluation of MSD and KSPC, and a new unified error metric**. Soukoreff & MacKenzie. CHI, 2003. https://doi.org/10.1145/642611.642632
  It defines total error rate, including corrected errors.
- [should] **Phrase sets for evaluating text entry techniques**. MacKenzie & Soukoreff. CHI Extended Abstracts, 2003. https://doi.org/10.1145/765891.765971
  It gives the standard phrase set for text-entry tests.
- [should] **Complementing text entry evaluations with a composition task**. Vertanen & Kristensson. *ACM TOCHI*, 2014. https://doi.org/10.1145/2555691
  It argues for tests where users compose their own text, not only copy text.
- [should] **Natural language processing with dynamic classification improves P300 speller accuracy and bit rate**. Speier et al. *Journal of Neural Engineering*, 2012. https://doi.org/10.1088/1741-2560/9/1/016004
  It is an early language-model-assisted BCI speller.
- [optional] **A versatile dataset for text entry evaluations based on genuine mobile emails**. Vertanen & Kristensson. MobileHCI, 2011. https://doi.org/10.1145/2037373.2037418
  It gives realistic phrases for simulated users.
- [optional] **Performance comparisons of phrase sets and presentation styles for text entry evaluations**. Kristensson & Vertanen. IUI, 2012. https://doi.org/10.1145/2166966.2166972
  It shows that phrase choice changes text-entry results.
- [optional] **Dasher—a data entry interface using continuous gestures and language models**. Ward, Blackwell, MacKay. UIST, 2000. https://doi.org/10.1145/354401.354427
  It is the classic language-model-driven text entry design.
- [optional] **Brain–Computer Interface With Language Model–Electroencephalography Fusion for Locked-In Syndrome**. Oken et al. *Neurorehabilitation and Neural Repair*, 2014. https://doi.org/10.1177/1545968313516867
  RSVP Keyboard. It fuses EEG evidence and an LM prior in a Bayesian way.
- [optional] **Language Model Applications to Spelling with Brain-Computer Interfaces**. Mora-Cortes et al. *Sensors*, 2014. https://doi.org/10.3390/s140405967
  It reviews LM use in BCI spellers.
- [optional] **Which Metric Reflects the Spelling Rate Accuracy in Event-Related Potential-Based Brain-Computer Interfaces?** Bekhelifi & Mebtouche. arXiv, 2026. https://arxiv.org/abs/2607.00794
  It compares speller metrics. It is a recent check for our metric choice.
- [optional] **RAS: a Reliability Oriented Metric for Automatic Speech Recognition**. Huang et al. arXiv, 2026. https://arxiv.org/abs/2604.24278
  It rewards abstention in ASR scoring. It is close in spirit to eWPM.

## 9. Benchmarks, toolkits and foundation models for non-invasive BCI

- [should] **NeuralBench: A Unifying Framework to Benchmark NeuroAI Models**. Banville, d'Ascoli, Dahan et al. arXiv, 2026. https://arxiv.org/abs/2605.08495
  It is Meta's benchmark framework. Our layer can report on its tasks.
- [should] **LibriBrain: Over 50 Hours of Within-Subject MEG to Improve Speech Decoding Methods at Scale**. Özdogan et al. arXiv, 2025. https://arxiv.org/abs/2506.02098
  It is a large public MEG dataset. It is a second MEG test set.
- [should] **The 2025 PNPL Competition: Speech Detection and Phoneme Classification in the LibriBrain Dataset**. Landau et al. arXiv, 2025. https://arxiv.org/abs/2506.10165
  It defines public MEG decoding tasks and baselines.
- [should] **MEG-XL: Data-Efficient Brain-to-Text via Long-Context Pre-Training**. Jayalath & Parker Jones. ICML, 2026. https://arxiv.org/abs/2602.02494
  It is a MEG brain-to-text foundation model. It is a second decoder for our layer.
- [optional] **BrainOmni: A Brain Foundation Model for Unified EEG and MEG Signals**. Xiao et al. NeurIPS, 2025. https://arxiv.org/abs/2505.18185
  It pretrains one model on EEG and MEG.
- [optional] **REVE: A Foundation Model for EEG — Adapting to Any Setup with Large-Scale Pretraining on 25,000 Subjects**. El Ouahidi et al. NeurIPS, 2025. https://arxiv.org/abs/2510.21585
  It is a large EEG foundation model for any electrode layout.
- [optional] **Large Brain Model for Learning Generic Representations with Tremendous EEG Data in BCI**. Jiang, Zhao, Lu. ICLR, 2024. https://arxiv.org/abs/2405.18765
  LaBraM. It is a common EEG foundation-model baseline.
- [optional] **CBraMod: A Criss-Cross Brain Foundation Model for EEG Decoding**. Wang et al. ICLR, 2025. https://arxiv.org/abs/2412.07236
  It is another strong EEG foundation-model baseline.
- [optional] **Deep learning with convolutional neural networks for EEG decoding and visualization**. Schirrmeister et al. *Human Brain Mapping*, 2017. https://doi.org/10.1002/hbm.23730
  It is the Braindecode paper. Braindecode is the main deep-learning toolkit for EEG/MEG.
- [optional] **MOABB: trustworthy algorithm benchmarking for BCIs**. Jayaram & Barachant. *Journal of Neural Engineering*, 2018. https://doi.org/10.1088/1741-2552/aadea0
  It gives reproducible BCI benchmarks.
- [optional] **The Lab Streaming Layer for Synchronized Multimodal Recording**. Kothe et al. bioRxiv, 2024. https://doi.org/10.1101/2024.02.13.580071
  LSL is the standard real-time stream transport. A live demo would use it.
- [optional] **Apple unveils powerful accessibility features coming later this year**. Apple Newsroom (press release), 13 May 2025. https://www.apple.com/newsroom/2025/05/apple-unveils-powerful-accessibility-features-coming-later-this-year/
  It announces a protocol for Switch Control with BCIs (the BCI HID profile). Our layer's output could feed it. This is not a paper.

---

## Unverified leads

- **Brain-to-Text '25 benchmark paper.** We found no official "lessons learned" paper for the '25 competition. The task uses the Card et al. 2024 data on Kaggle. The '25 results appear only in third-party papers (Zhang et al. 2025; Boccato et al. 2026, above).
- **Hystoc (ICASSP 2024).** A search result showed a VUT Brno PDF on word-level confidence for end-to-end ASR. We did not confirm the authors or title, so we left it out.
- **"Characters per minute" / "output characters per minute" speller metrics.** Search snippets credit these metrics to specific papers. We did not confirm which paper introduced each one.
