# 📈 Stock Market Price Modelling & Analyst

A web-based **stock analysis and market intelligence application** built with Python and Flask.

The application brings together stock prices, financial ratios, quarterly results, company information, news headlines, and financial documents to provide a consolidated view of a company. It combines **rule-based financial analysis** with optional **AI-generated narratives** to make the analysis easier to understand.

> ⚠️ **Disclaimer:** This project is for educational and informational purposes only. It is not financial advice, and its analysis should not be used as the sole basis for investment decisions.

---

## 🚀 Features

### 📊 Stock Market Data

* Fetches current and historical stock market information.
* Retrieves price and volume data.
* Supports analysis of publicly available market information.

### 💰 Financial Analysis

The application collects and analyzes financial information such as:

* Revenue
* Profit
* Profit margins
* P/E ratio
* P/B ratio
* ROE
* ROCE
* Debt-related metrics
* Quarterly performance
* Other company fundamentals

### 📰 News & Market Information

The application retrieves relevant news headlines to provide additional context around a company's recent performance.

### 📄 Company Documents

The application can work with publicly available company information and financial documents, including:

* Annual reports
* Quarterly results
* Investor presentations
* Earnings/conference call information
* Company filings

### 🤖 AI-Powered Analysis

The core analysis is rule-based, with optional AI-generated narrative analysis.

If an `ANTHROPIC_API_KEY` is configured, the application can generate a written explanation of the financial analysis using Anthropic's API.

Without an API key, the application can still perform its rule-based analysis.

### 💬 Stock Analyst Chat Interface

The Flask web application provides an interactive interface where users can enter a company/stock and receive an analysis based on the available market and financial data.

---

## 🏗️ Project Architecture

```text
stock-market-price-modelling/
│
├── app.py                 # Flask application and web routes
├── analysis.py            # Financial analysis and scoring logic
├── scraper.py             # Data collection and web scraping
│
├── templates/
│   └── index.html         # Web application interface
│
├── requirements.txt       # Python dependencies
├── .gitignore             # Git ignored files
└── README.md              # Project documentation
```

### How the application works

```text
                User
                  │
                  ▼
          ┌───────────────┐
          │  Flask Web UI │
          └───────┬───────┘
                  │
                  ▼
          ┌───────────────┐
          │    app.py     │
          └───────┬───────┘
                  │
          ┌───────┴────────┐
          ▼                ▼
   ┌─────────────┐   ┌─────────────┐
   │  scraper.py │   │ analysis.py │
   └──────┬──────┘   └──────┬──────┘
          │                  │
          ▼                  ▼
   Market & Financial   Rule-Based
       Data             Analysis
          │                  │
          └────────┬─────────┘
                   ▼
          ┌─────────────────┐
          │ Optional AI     │
          │ Narrative       │
          └────────┬────────┘
                   │
                   ▼
             Final Analysis
```

---

## 🔎 Data Sources

The application combines information from multiple publicly available sources.

| Source              | Information                                                 |
| ------------------- | ----------------------------------------------------------- |
| **Yahoo Finance**   | Stock prices, historical prices and volume                  |
| **Screener.in**     | Financial ratios, quarterly results and company information |
| **Company Website** | Investor relations, results and corporate information       |
| **Google News RSS** | Recent news headlines                                       |

The repository currently documents these sources as part of its data collection pipeline.

---

## 🛠️ Technologies Used

* **Python**
* **Flask**
* **HTML/CSS/JavaScript**
* **Pandas**
* **Yahoo Finance**
* **Screener.in**
* **Google News RSS**
* **Anthropic API** *(optional)*

---

## 📋 Requirements

* Python 3.10+
* `pip`
* Internet connection
* Optional: Anthropic API key for AI-generated analysis

---

## ⚙️ Installation

### 1. Clone the repository

```bash
git clone https://github.com/mannancodex/stock-market-price-modelling.git
cd stock-market-price-modelling
```

### 2. Create a virtual environment

#### Windows

```powershell
python -m venv venv
venv\Scripts\activate
```

#### macOS/Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## ▶️ Running the Application

Start the Flask application:

```bash
python app.py
```

The application should be available at:

```text
http://127.0.0.1:5000
```

Open that address in your browser.

---

## 🤖 Optional AI Configuration

The application supports an optional Anthropic API integration for generating a natural-language explanation of the rule-based analysis.

### Windows PowerShell

```powershell
$env:ANTHROPIC_API_KEY="your_api_key_here"
```

### Windows CMD

```cmd
set ANTHROPIC_API_KEY=your_api_key_here
```

### macOS/Linux

```bash
export ANTHROPIC_API_KEY="your_api_key_here"
```

Then start the application:

```bash
python app.py
```

The application will continue to work without the API key using its rule-based analysis functionality.

---

## 📈 Analysis Pipeline

The application follows a multi-stage analysis process:

### 1. Data Collection

The scraper collects available information about the requested company from financial and news sources.

### 2. Data Processing

Raw financial and market information is cleaned and organized into structured data.

### 3. Fundamental Analysis

The application evaluates relevant financial metrics and company performance.

### 4. Rule-Based Scoring

Financial indicators are used to generate analytical signals and an overall assessment.

### 5. News & Context

Recent news and company information are incorporated to provide additional context.

### 6. Optional AI Narrative

When configured, the Anthropic API converts the analytical output into a more readable written explanation.

### 7. Web Presentation

The final analysis is displayed through the Flask web interface.

---

## 🎯 Project Objectives

The main objectives of this project are:

* Build a practical stock-analysis application using Python.
* Combine financial, market and news data in one interface.
* Automate basic fundamental analysis.
* Make financial information easier to interpret.
* Demonstrate web scraping and data-processing techniques.
* Integrate AI into a financial analysis workflow.
* Provide a foundation for further stock prediction and modelling research.

---

## 🔮 Future Improvements

Potential future improvements include:

* 📈 Machine-learning-based stock price prediction
* 🧠 LSTM/Transformer time-series models
* 📊 Interactive historical price charts
* 📉 Technical indicators such as RSI, MACD and Bollinger Bands
* 💹 Portfolio tracking
* 🔔 Price and news alerts
* 📰 Sentiment analysis of financial news
* 🏢 Peer/company comparison
* 📑 Automated annual-report analysis
* 🧪 Backtesting of trading strategies
* ☁️ Cloud deployment
* 🔐 Secure API-key management
* 📱 Improved responsive UI

---

## 📂 Main Components

### `app.py`

The main Flask application.

Responsible for:

* Starting the web server
* Handling HTTP requests
* Managing application routes
* Connecting the frontend with the analysis pipeline
* Returning analysis results to the user

### `scraper.py`

Responsible for collecting external information.

It works with sources such as:

* Yahoo Finance
* Screener.in
* Company websites
* Google News RSS

### `analysis.py`

Contains the financial analysis logic.

It processes the collected data and produces analytical results that can be displayed through the application.

### `templates/index.html`

Contains the frontend interface for interacting with the stock analyst application.

---

## 🧪 Example Workflow

A typical user workflow looks like this:

```text
1. Open the application
        ↓
2. Enter a company/stock
        ↓
3. Application collects market data
        ↓
4. Financial information is retrieved
        ↓
5. Recent news is collected
        ↓
6. Financial metrics are analyzed
        ↓
7. Rule-based assessment is generated
        ↓
8. Optional AI narrative is generated
        ↓
9. Results are displayed
```

---

## 🌐 Deployment

The application can be deployed to platforms that support Python/Flask applications, such as:

* Railway
* Render
* PythonAnywhere
* AWS
* Google Cloud
* Azure

For production deployment, use a production WSGI server such as **Gunicorn** rather than Flask's development server.

Example:

```bash
gunicorn app:app
```

---

## 🔒 Security

Never commit API keys or other secrets to GitHub.

Add environment files to `.gitignore`:

```text
.env
*.env
```

Use environment variables for sensitive configuration.

---

## ⚠️ Disclaimer

This project is intended for **educational, research and demonstration purposes**.

Stock prices and financial information can change rapidly. Data obtained from third-party sources may be delayed, incomplete or inaccurate.

The analysis generated by this application should **not be considered financial, investment, legal or professional advice**.

Always conduct independent research and consult a qualified financial professional before making investment decisions.

---

## 👨‍💻 Author

**Mannan Codex**

GitHub:
https://github.com/mannancodex

Project:
https://github.com/mannancodex/stock-market-price-modelling

---

## ⭐ Contributing

Contributions, suggestions and improvements are welcome.

To contribute:

```bash
git clone https://github.com/mannancodex/stock-market-price-modelling.git
cd stock-market-price-modelling
```

Create a feature branch:

```bash
git checkout -b feature/your-feature
```

Make your changes, commit them and open a pull request.

---

## 📜 License

This project currently does not specify a license.

If you intend to make the project open source, consider adding an appropriate license such as the MIT License.
