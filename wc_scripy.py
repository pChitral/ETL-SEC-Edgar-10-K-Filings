import os
import pandas as pd
from bs4 import BeautifulSoup
from supabase import create_client
from dotenv import load_dotenv

from utils.get_ticker_10k_filings import get_ticker_10k_filings
from utils.collect_ticker_files import collect_ticker_files
from utils.delete_txt_files import delete_txt_files

from shutil import rmtree
from collections import Counter
import json

# Supabase API keys
load_dotenv()
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def extract_mdna_section(content):
    soup = BeautifulSoup(content, "html.parser")
    mda_start = soup.find(string=lambda text: "ITEM 7." in text)
    if not mda_start:
        return "MD&A section not found."

    mda_content = []
    for sibling in mda_start.find_all_next(string=True):
        if "ITEM 8." in sibling:
            break
        clean_str = sibling.strip()
        if clean_str:
            mda_content.append(clean_str)

    return " ".join(mda_content).replace("\n", " ").replace("\t", " ").strip()


# Read the words from the provided file
with open("/mnt/data/words_fraud_constraints.json", "r") as file:
    target_words = json.load(file)


def get_word_frequencies(text):
    words = text.split()
    frequency = Counter(words)
    target_frequencies = {
        word: frequency[word] for word in target_words if word in frequency
    }
    return json.dumps(target_frequencies)


def parse_html_file(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()
    mda_section = extract_mdna_section(content)
    return {"MD&A": mda_section, "word_frequency": get_word_frequencies(mda_section)}


def new_10k_reports_to_supabase(parsed_data_list, client):
    for data in parsed_data_list:
        response = client.table("reports_10k").insert(data).execute()
        if response.status_code != 201:
            print(
                f"Failed to insert data for {data['ticker']} - {data['accession_number']}: {response.text}"
            )


def process_ticker_10k_data(ticker):
    try:
        get_ticker_10k_filings(ticker)
    except Exception as e:
        print(f"Error occurred while downloading filings for {ticker}: {e}")
        return {}

    ticker_files_dict = collect_ticker_files()
    delete_txt_files(ticker_files_dict.get(ticker, []))

    all_parsed_data = {}
    for html_file in ticker_files_dict.get(ticker, []):
        if html_file.endswith(".html"):
            path_parts = html_file.split("/")
            cik_year_acc = path_parts[4].split("-")

            if len(cik_year_acc) < 3:
                print(f"Skipping file with unexpected format: {html_file}")
                continue

            CIK = cik_year_acc[0]
            # Convert the two-digit year to four digits
            two_digit_year = cik_year_acc[1]
            if (
                int(two_digit_year) > 50
            ):  # Assuming we're starting from 1950 for simplicity
                Year = "19" + two_digit_year
            else:
                Year = "20" + two_digit_year
            AccessionNumber = cik_year_acc[2]
            try:
                parsed_data = parse_html_file(html_file)
            except Exception as e:
                print(f"Could not parse {html_file} due to error: {e}")
                continue

            try:
                filing_dict = {
                    "ticker": ticker,
                    "cik": CIK,
                    "year": int(Year),
                    "accession_number": AccessionNumber,
                    "mda_section": parsed_data.get("MD&A", "Section not found"),
                    "word_frequency": parsed_data.get("word_frequency", "{}"),
                }
            except ValueError:
                print(f"Skipping file with invalid year format in {html_file}")
                continue

            all_parsed_data[AccessionNumber] = filing_dict

    all_parsed_data_list = list(all_parsed_data.values())
    new_10k_reports_to_supabase(all_parsed_data_list, Client)
    # Clear the data folder after processing
    if os.path.exists("data"):
        rmtree("data")
    return all_parsed_data


df = pd.read_json("company_tickers.json", orient="index")
all_tickers_data = {}
tickers = df["ticker"].tolist()
count = 0
for ticker in tickers:
    all_tickers_data[ticker] = process_ticker_10k_data(ticker)
    count += 1
    if count > 3:
        break
