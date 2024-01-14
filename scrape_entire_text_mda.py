# Standard library imports for concurrency, file operations, and data handling
import concurrent.futures
import os
import pandas as pd
import logging
import random
import time

# Utility functions from the utils module for specific operations
from utils.processing.process_single_ticker import process_single_ticker
from utils.helpers.log_memory_usage import log_memory_usage
from utils.helpers.download_filings_for_batch import (
    download_filings_for_batch,
)  # New import

# Set up basic configuration for logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("ticker_processing.log"), logging.StreamHandler()],
)

# Define the batch size for processing tickers
BATCH_SIZE = 10

if __name__ == "__main__":
    # Load company tickers data from the status file
    status_df = pd.read_csv("processing_status.csv")

    logging.info("Starting the processing of tickers.")

    # Filter out already processed tickers
    to_process_df = status_df[status_df["processed"] == False]

    # Set the total number of tickers to process
    total_tickers = len(to_process_df)
    all_tickers_data = []

    # Loop through tickers in batches for processing
    for batch_start in range(0, total_tickers, BATCH_SIZE):
        # Log the memory usage before processing the batch
        log_memory_usage()

        # Introduce a random sleep time between batches
        sleep_time = random.uniform(1, 2)
        time.sleep(sleep_time)

        # Determine the end of the current batch
        batch_end = min(batch_start + BATCH_SIZE, total_tickers)
        tickers_batch = to_process_df.iloc[batch_start:batch_end]

        # Extract CIKs for the current batch
        cik_list = [row["cik_str"] for _, row in tickers_batch.iterrows()]

        # Download filings for the current batch of CIKs
        download_filings_for_batch(cik_list)

        # Process tickers in the current batch concurrently
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(
                    process_single_ticker,
                    row["ticker"],
                    row["cik_str"],
                    row["title"],
                )
                for index, row in tickers_batch.iterrows()
            ]

            # Collect results from futures as they complete
            for future in concurrent.futures.as_completed(futures):
                result, cik, ticker = future.result()
                if result is not None and not result.empty:
                    # Create directory for ticker data if it doesn't exist
                    os.makedirs("ticker_data", exist_ok=True)

                    # Save the processed data to a Parquet file
                    result.to_parquet(f"ticker_data/{ticker}.parquet", index=False)
                    all_tickers_data.append(result)

                    # Log the processing of the ticker
                    logging.info(f"Processed ticker: {ticker}")
                    # Update the status file to mark the ticker as processed
                    status_df.loc[status_df["ticker"] == ticker, "processed"] = True



        # Log the percentage of tickers processed so far
        processed_percentage = (batch_end / total_tickers) * 100
        logging.info(
            f"Completed {processed_percentage:.2f}% (Processed {batch_end} of {total_tickers} tickers)"
        )
    log_memory_usage()

    # Log completion of data processing
    logging.info("All ticker data processed and exported.")
