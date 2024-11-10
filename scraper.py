import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
from bs4 import BeautifulSoup
import csv
from typing import List, Dict

def fetch_and_parse_page(driver, page_number: int) -> List[Dict[str, str]]:
    """Fetch the current page's HTML content and parse it to extract the data."""
    html_content = driver.page_source
    return parse_html(html_content, page_number)

def parse_html(html_content: str, page_number: int) -> List[Dict[str, str]]:
    """Parse the HTML to extract data using structured tags and return a list of dictionaries."""
    soup = BeautifulSoup(html_content, 'html.parser')
    articles = soup.find_all('article', class_='ng-star-inserted')
    data_list = []

    for article in articles:
        data = {}
        permit_id = article.find('p', class_='ecl-u-type-bold').get_text(strip=True)
        if permit_id:
            data['permit_id'] = permit_id

        info_paragraphs = article.find_all('p', class_='ecl-u-type-paragraph-m')
        for paragraph in info_paragraphs:
            span = paragraph.find('span', class_='ecl-u-type-bold')
            if span:
                key = span.text[:-1]  # Remove the colon at the end
                value = paragraph.get_text(strip=True).replace(span.text, '', 1).strip()

                if key == "Air carrier Name (Code)":
                    # Split based on ' - ' and handle cases with multiple parts
                    parts = value.split(' - ')
                    if len(parts) >= 2:
                        air_carrier_name = parts[-2].strip()  # Second to last part is the name
                        air_carrier_code = parts[-1].strip("()")  # Last part is the code without parentheses
                        data['air_carrier_name'] = air_carrier_name
                        data['air_carrier_code'] = air_carrier_code
                    else:
                        print(f"Unexpected format in 'Air carrier Name (Code)' on page {page_number}: {value}")

                elif key == "Airport Name (Code)":
                    # Split based on ' - ' and handle cases with multiple parts
                    parts = value.split(' - ')
                    if len(parts) >= 2:
                        airport_name = " - ".join(parts[:-1]).strip()  # All parts except the last are the name
                        airport_code = parts[-1].strip("()")  # Last part is the code without parentheses
                        data['airport_name'] = airport_name
                        data['airport_code'] = airport_code
                    else:
                        print(f"Unexpected format in 'Airport Name (Code)' on page {page_number}: {value}")

                else:
                    data[key.lower().replace(' ', '_')] = value  # Normalize the keys to snake_case

        if data:
            data_list.append(data)

    return data_list

def fetch_and_write_data(url: str, csv_filename: str, checkpoint_file: str) -> None:
    """Fetch data page by page, write to CSV periodically, and handle resumption on crash."""
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

    # Determine where to resume from if checkpoint file exists
    start_page = 1
    if os.path.exists(checkpoint_file):
        with open(checkpoint_file, 'r') as f:
            start_page = int(f.read().strip())

    try:
        driver.get(url)
        time.sleep(5)  # Initial wait for the first page to load

        # Skip to the starting page
        current_page = 1
        while current_page < start_page:
            try:
                next_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//span[contains(@class, 'ecl-link__label') and text()='Next']"))
                )
                ActionChains(driver).move_to_element(next_button).perform()
                next_button.click()
                time.sleep(5)  # Wait for the next page to load
                current_page += 1
            except Exception:
                print(f"Failed to navigate to page {start_page}.")
                return  # Exit if we can't reach the start page

        # Open CSV in append mode and write headers only if the file is new
        file_exists = os.path.isfile(csv_filename)
        with open(csv_filename, 'a', newline='') as csvfile:
            csv_columns = ['permit_id', 'member_state', 'air_carrier_name', 'air_carrier_code', 'airport_name', 'airport_code', 'airport_country']
            writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
            if not file_exists:
                writer.writeheader()

            # Loop through pages and write data
            while True:
                # Fetch, parse, and write current page's data
                page_data = fetch_and_parse_page(driver, current_page)
                writer.writerows(page_data)

                # Update checkpoint file
                with open(checkpoint_file, 'w') as f:
                    f.write(str(current_page))

                # Find and click the 'Next' button to go to the next page
                try:
                    next_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, "//span[contains(@class, 'ecl-link__label') and text()='Next']"))
                    )
                    ActionChains(driver).move_to_element(next_button).perform()
                    next_button.click()
                    time.sleep(5)  # Wait for the next page to load
                    current_page += 1
                except Exception:
                    print("No more pages to scrape.")
                    break

    finally:
        driver.quit()

def main():
    url = "https://ksda.ec.europa.eu/public/acc3s?status=Valid"
    csv_filename = "acc3_data.csv"
    checkpoint_file = "acc3_checkpoint.txt"
    fetch_and_write_data(url, csv_filename, checkpoint_file)
    print("Data extraction and writing to CSV completed successfully.")

if __name__ == "__main__":
    main()
