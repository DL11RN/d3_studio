# d3 Studio

*English: [README.md](README.md)*

Una piccola web app locale per lavorare con il [modello decisionale **d3** di Ollama](https://ollama.com/library/d3): definisci le domande una volta, dai in input testo, righe di CSV, immagini o PDF e ottieni risposte con probabilità per ogni elemento, in tabella, schede, grafici o come verdetto per documento. Niente cloud, niente account, niente dipendenze da installare.

d3 non conversa. Gli dai un input (`state`) e un elenco di domande, e per ciascuna restituisce una decisione:

| Tipo di domanda | Cosa definisci | Cosa restituisce d3 |
|---|---|---|
| **Sì / No** (`noul`) | cosa significano «sì» e «no» | probabilità del *sì* |
| **Scelta** (`choice`) | un insieme di opzioni, ciascuna con una descrizione | l'opzione migliore e una probabilità per ogni opzione |
| **Scala** (`score`) | livelli ordinati (es. Basso, Medio, Alto) | il livello scelto |

Usi tipici: smistare righe di log o ticket di assistenza, instradare messaggi, controllare se una foto contiene persone o occhiali, decidere se un PDF parla di un certo argomento.

> L'interfaccia è in **italiano**. Le domande da porre al modello possono essere scritte in qualunque lingua che d3 comprenda.

## Funzioni

- **Editor di domande** con i tre tipi, set pronti (triage di log di sicurezza, controlli sulle foto, smistamento di richieste di supporto, «questo PDF parla di medicina?») e set personali, che si possono salvare, esportare e importare in JSON.
- **Input**: testo incollato (un elemento per riga o separato da righe vuote), **CSV** (rilevamento del separatore, scelta delle colonne da inviare, colonna etichetta facoltativa), **immagini** (ridimensionate nel browser), **PDF** (testo diviso in blocchi, oppure pagine inviate come immagini per i documenti scansionati).
- **Risultati**: tabella, schede, grafici, JSON grezzo e una vista **Documenti** per i PDF con verdetto sì/no per file (regola: massimo, media o maggioranza dei blocchi). Soglia regolabile, ricerca, ordinamento, export CSV/JSON.
- **Anteprima della richiesta** e pulsante per copiarla come `curl`, per riusare la stessa richiesta altrove.
- Esegue più richieste in parallelo, mostra velocità e tempo stimato, gestisce CSV grandi con la paginazione.

## Requisiti

- **Ollama 0.40.9 o successivo**, con un modello d3 scaricato: `ollama pull d3` (il predefinito è il 4B; esistono anche `d3:2b`, `d3:9b` e `d3:27b`, dimensioni nella [pagina del modello](https://ollama.com/library/d3)).
- **Python 3.8+**. Solo libreria standard: non c'è nulla da installare con `pip`, quindi non serve un ambiente virtuale.
- Un browser recente.
- *Facoltativo, per i PDF:* **poppler** (`pdftotext`, `pdftoppm`).
  - Debian/Ubuntu: `sudo apt install poppler-utils`
  - macOS: `brew install poppler`
  - Windows: installa una build di Poppler e aggiungi la cartella `bin` al `PATH`

  Sviluppato e provato su Linux. macOS e Windows dovrebbero funzionare (non c'è nulla di specifico di una piattaforma) ma non sono stati provati.

## Avvio rapido

```bash
git clone https://github.com/<tuo-utente>/d3-studio.git
cd d3-studio
ollama pull d3
python3 d3_studio.py --open
```

Poi apri **http://127.0.0.1:8765** (`--open` lo fa da solo). Aprila da questo indirizzo e non con un doppio clic sul file HTML: la pagina ha bisogno del server locale per raggiungere Ollama.

Ollama su un'altra macchina o su un'altra porta:

```bash
python3 d3_studio.py --ollama http://OLLAMA_HOST:11434 --port 8766
```

| Opzione | Predefinito | Significato |
|---|---|---|
| `--ollama URL` | `http://localhost:11434` | Dove ascolta Ollama |
| `--port N` | `8765` | Porta dell'interfaccia web |
| `--timeout S` | `300` | Secondi di attesa per ogni richiesta |
| `--open` | spento | Apre il browser all'avvio |
| `--host ADDR` | `127.0.0.1` | Indirizzo di ascolto (vedi Sicurezza: lascialo così) |

## Come si usa

1. **Domande**: carica un set pronto o creane uno. Per ogni domanda scrivi l'istruzione e, per i sì/no, cosa significano *sì* e *no*; per le scelte, le opzioni e cosa vuol dire ciascuna. Più le descrizioni sono concrete, migliori sono le risposte.
2. **Input**: incolla testo, trascina un CSV, immagini o PDF. Scegli il modello in alto (l'elenco viene dal tuo Ollama) e il numero di richieste in parallelo, poi premi **Esegui**.
3. **Risultati**: leggi l'output nella vista che preferisci, imposta la soglia per le domande sì/no, esporta in CSV o JSON.

### Consigli

- **Ogni domanda è un passaggio separato sull'input.** Il tempo cresce con il numero di domande: tieni solo quelle che servono.
- **Il contesto è di 4.096 token** nei pacchetti d3 di Ollama, e Ollama non tronca: gli elementi lunghi vanno accorciati. L'impostazione *Limite caratteri per elemento* taglia ogni testo prima dell'invio; i PDF vengono divisi in blocchi per lo stesso motivo.
- **Soglia e regole.** Per un sì/no a livello di documento, *massimo* risponde a «una parte corrisponde?», *maggioranza* a «parla soprattutto di questo?».
- **Velocità.** Controlla `ollama ps`: il modello deve stare al 100% su GPU. Se una parte è su CPU, usa una variante più piccola, chiudi gli altri modelli o riduci le domande.
- **PDF scansionati**: non hanno testo; usa *Pagine come immagini*. È più lento e usa più contesto.

### Usare la stessa API senza interfaccia

Il pulsante «Anteprima richiesta» mostra la richiesta esatta per il primo elemento. In sostanza:

```bash
curl -s http://localhost:11434/v1/systemone -H 'Content-Type: application/json' -d '{
  "model": "d3",
  "state": "Il cliente scrive: mi è stato addebitato due volte questo mese.",
  "questions": {
    "team": {"type": "choice", "instructions": "Which team should handle this request?",
             "criteria": {"billing": "Invoices and charges", "technical": "App errors and faults"}}
  }
}'
```

## Privacy e sicurezza

- **I dati restano sul tuo computer.** La pagina non carica nulla da internet e non invia telemetria. Gli elementi vanno solo all'indirizzo di Ollama che hai configurato, passando dal server locale.
- Il browser conserva solo **domande, set salvati e impostazioni** (in `localStorage`). I risultati stanno solo in memoria e si perdono chiudendo o ricaricando la pagina: esportali prima.
- Il server ascolta solo su `127.0.0.1`, rifiuta richieste con `Host` o `Origin` non locali, inoltra solo gli endpoint necessari (`/v1/systemone`, `/api/tags`, `/api/version`) e **non ha autenticazione**. Non esporlo su una rete; per l'uso da remoto fai un tunnel SSH della porta (`ssh -L 8765:127.0.0.1:8765 host`).
- I PDF sono elaborati dagli strumenti poppler in una cartella temporanea che viene cancellata subito dopo.
- Le risposte del modello sono probabilistiche. Per decisioni di sicurezza, mediche o legali usale come supporto allo smistamento, non come verdetto.

## Problemi comuni

| Sintomo | Causa probabile |
|---|---|
| *NetworkError when attempting to fetch resource* | La pagina è stata aperta come file, oppure il server non è in esecuzione. Avvia `d3_studio.py` e usa `http://127.0.0.1:8765`. |
| Pallino rosso, «Ollama non raggiungibile» | Ollama non è in esecuzione o `--ollama` punta a un indirizzo sbagliato. |
| Modello non trovato / non scaricato | Esegui `ollama pull d3`, oppure scegli una variante d3 installata nel campo modello. |
| PDF: «pdftotext non trovato» | Installa poppler (vedi Requisiti) e riavvia il server. |
| Tabella vuota anche se tutte le righe sono completate | È attivo il filtro *solo sopra soglia*; vale solo per le domande sì/no. |
| Molto lento | Vedi *Velocità* sopra. |

## Struttura del progetto

```
d3_studio.py     server locale: serve l'interfaccia, inoltra a Ollama, estrae testo/pagine dai PDF
d3_studio.html   tutta l'interfaccia (un solo file, nessun framework, nessuna build)
```

## Licenza e crediti

Rilasciato con [licenza MIT](LICENSE).

d3 è una famiglia di modelli del progetto vLLM Semantic Router, distribuita tramite Ollama con licenza Apache-2.0. d3 Studio è uno strumento indipendente e non è affiliato né approvato da Ollama o dal progetto vLLM Semantic Router.
