# Career Venture Lab — Johnnykirk (AER-3 Drone Inspection Service)

Stage 1 Streamlit business simulation dashboard for **Team Johnnykirk** (**AP Calculus — Advanced Level**, Pathway **AER-3: Drone Inspection Service**).

## Folder Structure

```text
johnnykirk-aer3/
├── app.py
├── requirements.txt
├── README.md
├── sample_data/
│   └── monthly_fixture.csv
└── tests/
    └── test_app.py
```

## Setup & Local Run

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run acceptance tests:
   ```bash
   pytest
   ```
3. Start the Streamlit dashboard:
   ```bash
   streamlit run app.py
   ```

## Render Deployment Command

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port $PORT
```
