from bs4 import BeautifulSoup
from utils.find_general_section import find_general_section


def parse_html_file(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        soup = BeautifulSoup(file.read(), "lxml")
    all_text = " ".join([tag.strip() for tag in soup.stripped_strings])
    risk_factors_section = find_general_section("Risk Factors", all_text)
    parsed_data = {
        "Risk Factors": risk_factors_section
        if risk_factors_section
        else "Section not found"
    }
    return parsed_data