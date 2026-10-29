# d3 Studio

*Italiano: [README.it.md](README.it.md)*

A small local web app for working with [Ollama's **d3** decision model](https://ollama.com/library/d3): define your questions once, feed it text, CSV rows, images or PDFs, and get per-item answers with probabilities, in a table, cards, charts or a per-document verdict. No cloud, no accounts, no dependencies to install.

d3 does not chat. You give it some input (`state`) and a list of questions, and for each question it returns a decision:

| Question type | You define | d3 returns |
|---|---|---|
| **Yes / No** (`noul`) | what "yes" and "no" mean | probability of *yes* |
| **Choice** (`choice`) | a set of options, each with a description | the best option and a probability for every option |
| **Scale** (`score`) | ordered levels (e.g. Low, Medium, High) | the chosen level |

Typical uses: triaging log lines or support tickets, routing messages, checking whether a photo contains people or glasses, deciding whether a PDF is about a given topic.

> The interface is currently in **Italian**. The model questions themselves can be written in any language d3 understands.

## Features

- **Question editor** with the three question types, ready-made sets (security-log triage, photo checks, support-ticket routing, "is this PDF about medicine?") and your own sets, which can be saved, exported and imported as JSON.
- **Inputs**: pasted text (one item per line or blank-line separated), **CSV** (delimiter detection, choose which columns are sent, optional label column), **images** (resized in the browser), **PDF** (text split into blocks, or pages sent as images for scanned documents).
- **Results**: table, cards, charts, raw JSON, and a **Documents** view for PDFs with a yes/no verdict per file (rule: maximum, mean or majority of the blocks). Adjustable threshold, search, sorting, CSV/JSON export.
- **Request preview** and a copy-as-`curl` button, to reuse the exact request elsewhere.
- Runs several requests in parallel, shows speed and ETA, handles large CSVs with pagination.

## Requirements

- **Ollama 0.40.9 or later**, with a d3 model pulled: `ollama pull d3` (the default is the 4B model; `d3:2b`, `d3:9b` and `d3:27b` also exist, see the [model page](https://ollama.com/library/d3) for sizes).
- **Python 3.8+**. Standard library only: there is nothing to `pip install`, so no virtual environment is needed.
- A modern browser.
- *Optional, for PDF input:* **poppler** (`pdftotext`, `pdftoppm`).
  - Debian/Ubuntu: `sudo apt install poppler-utils`
  - macOS: `brew install poppler`
  - Windows: install a Poppler build and add its `bin` folder to `PATH`

  Developed and tested on Linux. macOS and Windows should work (nothing is platform-specific) but have not been tested.

## Quick start

```bash
git clone https://github.com/DL11RN/d3-studio.git
cd d3-studio
ollama pull d3
python3 d3_studio.py --open
```

Then open **http://127.0.0.1:8765** (`--open` does it for you). Open it through this address and not by double-clicking the HTML file: the page needs the local server to reach Ollama.

Ollama on another machine, or another port:

```bash
python3 d3_studio.py --ollama http://OLLAMA_HOST:11434 --port 8766
```

| Option | Default | Meaning |
|---|---|---|
| `--ollama URL` | `http://localhost:11434` | Where Ollama is listening |
| `--port N` | `8765` | Port of the web UI |
| `--timeout S` | `300` | Seconds to wait for each request |
| `--open` | off | Open the browser at start |
| `--host ADDR` | `127.0.0.1` | Listen address (see Security: leave it as is) |

## How to use it

1. **Domande (Questions)**: load a ready-made set or create your own. For each question write the instruction and, for yes/no, what *yes* and *no* mean; for choices, the options and what each one means. The more concrete the descriptions, the better the answers.
2. **Input**: paste text, drop a CSV, images or PDFs. Choose the model at the top (the list comes from your Ollama) and the number of parallel requests, then press **Esegui (Run)**.
3. **Risultati (Results)**: read the output in the view that suits you, set the threshold for yes/no questions, export to CSV or JSON.

### Tips

- **Each question is a separate pass over the input.** Time grows with the number of questions: keep only the ones you need.
- **Context is 4,096 tokens** in the Ollama d3 packages, and Ollama does not truncate: long items must be shortened. The setting *Limite caratteri per elemento* (max characters per item) cuts each text before sending; PDFs are split into blocks for the same reason.
- **Threshold and rules.** For a document-level yes/no, *maximum* answers "does any part match?", *majority* answers "is it mostly about this?".
- **Speed.** Check `ollama ps`: the model should be on 100% GPU. If part of it is on CPU, use a smaller variant, close other models, or reduce the number of questions.
- **Scanned PDFs** have no text; use *Pagine come immagini* (pages as images). It is slower and uses more context.

### Calling the same API without the UI

The "Anteprima richiesta" (request preview) button shows the exact request for the first item. In essence:

```bash
curl -s http://localhost:11434/v1/systemone -H 'Content-Type: application/json' -d '{
  "model": "d3",
  "state": "Customer writes: I was charged twice this month.",
  "questions": {
    "team": {"type": "choice", "instructions": "Which team should handle this request?",
             "criteria": {"billing": "Invoices and charges", "technical": "App errors and faults"}}
  }
}'
```

## Privacy and security

- **Your data stays on your machine.** The page loads nothing from the internet and sends no telemetry. Items go only to the Ollama address you configured, through the local server.
- The browser stores only your **questions, saved sets and settings** (in `localStorage`). Results are kept in memory only and are lost when you close or reload the page, so export them first.
- The server listens on `127.0.0.1` only, rejects requests whose `Host` or `Origin` is not local, forwards only the endpoints it needs (`/v1/systemone`, `/api/tags`, `/api/version`) and has **no authentication**. Do not expose it on a network; for remote use, tunnel the port with SSH (`ssh -L 8765:127.0.0.1:8765 host`).
- PDFs are processed by the poppler tools in a temporary directory that is deleted right after.
- Model answers are probabilistic. For security, medical or legal decisions treat them as a triage aid, not as a verdict.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| *NetworkError when attempting to fetch resource* | The page was opened as a file, or the server is not running. Start `d3_studio.py` and use `http://127.0.0.1:8765`. |
| Red dot, "Ollama non raggiungibile" | Ollama is not running or `--ollama` points to the wrong address. |
| "model not found" / not downloaded | Run `ollama pull d3`, or pick an installed d3 variant in the model box. |
| PDF: "pdftotext non trovato" | Install poppler (see Requirements) and restart the server. |
| Table empty although all rows completed | The *solo sopra soglia* (only above threshold) filter is on; it applies to yes/no questions only. |
| Very slow | See *Speed* above. |

## Project layout

```
d3_studio.py     local server: serves the UI, proxies Ollama, extracts PDF text/pages
d3_studio.html   the whole UI (single file, no framework, no build step)
```

## License and credits

Released under the [MIT License](LICENSE).

d3 is a model family from the vLLM Semantic Router project, distributed through Ollama under Apache-2.0. d3 Studio is an independent tool and is not affiliated with or endorsed by Ollama or the vLLM Semantic Router project.
