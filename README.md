# GrepMind

## Grepmind Models

### GrepS

A decoder-only transformer language model specialised for code, built from scratch in PyTorch.

## Architecture

| Component | Choice | Why |
|---|---|---|
| Positional encoding | RoPE | Generalises to longer sequences than trained on |
| Feed-forward | SwiGLU | Outperforms ReLU/GELU on code tasks |
| Normalisation | RMSNorm (pre-norm) | More stable training than post-LayerNorm |
| Attention | Causal multi-head | Standard autoregressive setup |
| Tokeniser | Custom BPE | Trained on your own code corpus |
| Weight tying | embed ↔ lm_head | Fewer parameters, better perplexity |

Default config: `dim=2048, n_layers=16, n_heads=16` → ~1B parameters.

## Project structure

```
├── .venv/                     - virtual python environment
├── __pycache__/               - store .pyc files
├── models/                    - all models here
    ├── greps/                 - greps model here
        ├── config.py          — all hyperparameters in one dataclass
        ├── transformer.py     — RMSNorm, RoPE, SwiGLU, CausalAttention, TransformerDecoderLayer
        ├── bpe_engine.py      — custom BPE tokeniser
        ├── model.py           — full GrepS LM (stacks layers, adds generation)
        ├── dataset.py         — code file loader + sliding-window CodeDataset
        ├── train.py           — training loop (AdamW, cosine LR, mixed precision)
        ├── generate.py        — interactive REPL + single-prompt CLI
        └── data/              - data for training
            └── code/          — training code files here
├── static/                    - files to help render the html
    ├── img/                   - all logo images
    ├── authstyle.css          - style for sign in and sign up pages
    ├── grepstyle.css          - style for main page
    ├── grepscript.js          - functionality for all html
    ├── favicon.png            - favicon of grepmind
├── templates/                 - all html here
    ├── grep.html              - main site
    ├── security.html          - security dashboard
    ├── signin.html            - sign in page
    ├── signup.html            - sign up page
├── .env                       - sensitive info
├── .gitignore                 - files and folders to ignore when uploaded to git
├── README.md                  - this file
├── app.py                     - flask app
├── blocked_ips.json           - contains all blocked ips
├── security_log.json          - contains all security logs
├── users.json                 - contains all user info
├── requirements.txt           - libraries that python will install in virtual environment
├── test_bot.py                - webdriver bot used to test our recaptcha
```

More Models & Updates to come!

## Setup

```bash
pip install -r requirements.txt
```

## Quick start

### 1. Add training data

Put any code files (`.py`, `.js`, `.ts`, `.cpp`, `.java`, etc.) inside `data/code/`.
Subdirectories are fine. The more code, the better — aim for at least a few MB.

```
data/
└── code/
    ├── my_project/
    │   ├── main.py
    │   └── utils.py
    └── open_source/
        └── ...
```

### 2. Train

```bash
python train.py
```

Resume from a checkpoint:

```bash
python train.py --resume checkpoints/step_0010000.pt
```

Force CPU (if no GPU):

```bash
python train.py --device cpu
```

### 3. Generate

Interactive REPL:

```bash
python generate.py --checkpoint checkpoints/final.pt
```

Single prompt:

```bash
python generate.py --checkpoint checkpoints/final.pt --prompt "def merge_sort(arr):"
```

### Generation options

| Flag | Default | Description |
|---|---|---|
| `--temperature` | 0.8 | Lower = more predictable, higher = more creative |
| `--top_k` | 50 | Only sample from the top-K most likely tokens |
| `--top_p` | 0.95 | Nucleus sampling — cuts off the long tail |
| `--rep_penalty` | 1.1 | Penalises repeating the same tokens |
| `--max_tokens` | 256 | Maximum tokens to generate |

## Tuning tips

- **Too repetitive?** Increase `rep_penalty` (try 1.2–1.3)
- **Too random/nonsensical?** Lower `temperature` (try 0.5–0.6)
- **Cuts off too early?** Increase `--max_tokens`
- **Slow training?** Reduce `batch_size` or `seq_len` in `config.py`
- **Out of VRAM?** Reduce `dim` to 256 or `n_layers` to 4

## Hardware requirements

| Setup | Minimum |
|---|---|
| GPU training (recommended) | 8 GB VRAM |
| Apple Silicon (MPS) | 8 GB unified memory |
| CPU training (slow but works) | 16 GB RAM |
