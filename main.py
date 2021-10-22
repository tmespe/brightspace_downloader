# Downloads course content from brightspace and saves to disk
import argparse
import json
import logging
import os
import pathlib
import sys
import re
import zipfile
from time import sleep
from typing import Union, Optional, Dict

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import NoAlertPresentException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.firefox.options import Options

# Set up logging
logging.basicConfig(level=logging.DEBUG, filename='downloads.log', filemode='w',
                    format='%(asctime)s %(name)s - %(levelname)s - %(message)s')
logging.getLogger().addHandler(logging.StreamHandler())

# Load environment, set urls and save folders
load_dotenv()
LOGIN_URL = "https://emlyon.brightspace.com/"
BASE_URL = "https://emlyon.brightspace.com/d2l/le/content/"
save_folder = pathlib.Path.home() / "Documents/Em-lyon/brightspace"  # Save to user Documents folder
user = os.getenv("USER_NAME")
password = os.getenv("PASSWORD")

bootcamp_url = os.getenv("BOOTCAMP_URL")
bootcamp_user = os.getenv("BOOTCAMP_USER")
bootcamp_pass = os.getenv("BOOTCAMP_PASS")

# Add argument for setting directory to download content to
my_parser = argparse.ArgumentParser(description='Download course contents from brightspace')

my_parser.add_argument("-d",
                       "--directory",
                       metavar="arg_directory",
                       type=str,
                       help="name of text arg_file to search")

args = my_parser.parse_args()
if args.directory:
    save_folder = pathlib.Path(args.directory)
logging.info(f"Saving files to {save_folder}")

# Set download preferences for Firefox to make it download automatically with no dialogue
op = Options()
op.set_preference("browser.download.folderList", 2)
op.set_preference("browser.download.manager.showWhenStarting", False)
op.set_preference("browser.download.dir", str(save_folder))
op.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/x-zip-compressed")
op.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/zip")
op.headless = True

driver = webdriver.Firefox(options=op)


def open_course_list(filename: str = "courses.json") -> Union[dict]:
    """
    Opens a json file with courses that will be processed. The structure of the json should follow this format:
        {
            "courses": [
                {
                  "name": "Artificial intelligence in marketing",
                  "code": "210338"
                }
            ]
        }
    :param filename: Name of json file to look for courses
    :return: Returns a list of dicts with courses with "name", "url", "code" keys
    """
    with open(filename) as course_list:
        courses = json.load(course_list)["courses"]
    return courses


def check_if_alert() -> Optional[bool]:
    """
    Checks if javascript log in alert is present and waits for user to enter user and password manually
    and presses enter key to continue
    :return: True if alert is present None otherwise
    """
    try:
        alert = driver.switch_to.alert
        input("Press enter after entering username and password")
        return True
    except NoAlertPresentException:
        return


def log_in(user: str = user, password: str = password) -> None:
    """
    Logs in to brightspace with given username and password
    :param user: Brightspace username
    :param password: Brightspace password
    """
    # Check if username or password missing and exit if either missing
    if not user or not password:
        sys.exit("No username or password provided. Did you create a .env file with USER_NAME and PASSWORD?")

    # Select html xpath for username, password and sign in button
    user_xpath = '//*[@id="userNameInput"]'
    password_xpath = '//*[@id="passwordInput"]'
    sign_in_button = '//*[@id="submitButton"]'

    driver.get(LOGIN_URL)
    # Handle cases where on local emlyon network and an alert login pop up displays
    if not check_if_alert():
        # Find username, pasword and sign in elements and send keys for log in
        user_element = driver.find_element_by_xpath(user_xpath)
        password_element = driver.find_element_by_xpath(password_xpath)
        sign_in = driver.find_element_by_xpath(sign_in_button)
        user_element.send_keys(user)
        password_element.send_keys(password)
        sign_in.click()


def create_base_folder(folder=save_folder):
    # Make sure download folder exists and is set
    pathlib.Path(folder).mkdir(parents=True, exist_ok=True)
    os.chdir(folder)


def get_docs_from_non_xframe(course_name):
    """
    Gets course content from courses that do not use iframes
    :return: None
    """
    ignore_content = ["Table of Contents"]  # Elements to not download by name
    driver.implicitly_wait(2)
    units = driver.find_elements_by_xpath("//html/body/div[3]/div/div[1]/div[2]/div[1]/div/ul[2]/li")
    # Filter units to drop ignored
    units_filtered = filter(lambda x: re.sub(r'[^A-Za-z ]+', '', x.text) not in ignore_content, units)

    # Download all non_ignored units using dl_units passing xpath for units
    dl_units(course_name, units_filtered, {'find_element_by_xpath': '//button[text()="Download"]'})


def get_docs_from_course(url: str, course_name: str) -> None:
    """
    Gets course documents from brightspace learning platform and saves them to a course unit folder within
    the course name folder.
    :param url: Url of course content
    :param course_name: Name of course
    """
    create_base_folder()

    # Open and navigate to course content page
    driver.get(url)
    driver.implicitly_wait(5)
    # Page has iframe for contents. Select and switch to iframe
    frame_xpath = driver.find_elements_by_xpath('//iframe')
    try:
        driver.switch_to.frame(frame_xpath[0])
        driver.implicitly_wait(10)
    except IndexError:
        get_docs_from_non_xframe(course_name)

    # Content is divided into units. Get all units using class name
    all_units = driver.find_elements_by_class_name("unit")
    # Make sure units exist so only courses with content have folders created
    if all_units:
        # Create course folder and switch to it
        dl_units(course_name, all_units, {"find_element_by_class_name": "download-content-button"})
    else:
        pass


def dl_units(course_name: str, units: Union[object], dl_element: Dict[str, str]):
    """
    Downloads units from a brightspace content page
    :param course_name: Name of course
    :param units: An interable of units from course content to download
    :param dl_element: Dict with selenium find_by method and element to find:
            Ex {""find_element_by_class_name": "download-content-button""}
    :return: None
    """
    pathlib.Path(course_name).mkdir(parents=True, exist_ok=True)
    os.chdir(course_name)

    # Loop over all units on the content iframe and click download button and save
    for unit in units:
        # unit_name = unit.text.split("\n")[0]
        unit_name = unit.text.split("\n")[0]
        target_path = pathlib.Path(course_name) / pathlib.Path(unit_name)

        pathlib.Path(unit_name).mkdir(parents=True, exist_ok=True)
        unit.click()
        driver.implicitly_wait(2)  # Wait to make sure unit is loaded before clicking download
        logging.debug(f"Downloading {unit_name}")
        element_method = list(dl_element.keys())[0]
        element_name = list(dl_element.values())[0]
        try:
            download_btn = getattr(driver, element_method)(element_name)
            sleep(3)
            download_btn.click()
            sleep(45)
        except StaleElementReferenceException as e:
            download_btn = getattr(driver, element_method)(element_name)
            download_btn.click()
            sleep(45)
        except NoSuchElementException as e:
            if driver.find_element_by_tag_name("body").text:
                save_html_page(save_folder.joinpath(unit_name + ".html"), driver.page_source)
            else:
                logging.error(e)
                continue
        finally:
            # logging.debug("%s downloaded", unit_name)
            logging.debug(f"Finished processing {unit_name}")
            move_and_extract_files(target_path, zip_file_names=[course_name])
            clean_up_files(target_path)


def move_and_extract_files(destination_folder, source_folder=save_folder, zip_file_names=[],
                           extensions=[".zip", ".html", ".part"]) -> None:
    """
    Moves and extracts files with a given extension from source folder to destination folder
    :param zip_file_names: An optional list of file names to limit extraction to
    :param destination_folder: Folder to move files to
    :param source_folder: Folder to move files from
    :param extensions: Extension of files to move
    """
    files_to_folder = ["ipynb", "csv", "txt", "py"]  # Filetypes to extract to separate folders
    # Create set of files to loop over if suffix corresponds to extensions param
    files = {p.resolve() for p in pathlib.Path(source_folder).glob("*") if
             p.suffix in extensions}

    # Check if file.name is in zip_file_names to extract to avoid extracting leftover files to wrong folder
    if zip_file_names is not None:
        filtered_files = [file for file in files for name in zip_file_names if name in file.name]

    # Loop over either filtered files if param set or over files and extract to target folder
    for file in filtered_files or files:
        target_path = file.parent / destination_folder
        new_path = file.rename(target_path / file.name)
        if new_path.suffix == ".zip":
            logging.debug(f"Extracting {file} form {target_path} to {new_path}")
            print(f"Extracting {file} form {target_path} to {new_path}")

            zip_ref = zipfile.ZipFile(new_path)
            zip_names = zip_ref.namelist()
            if len(zip_names) > 15:  # Don't extract zip files with too many items
                continue
            # Loop over files in zip to check for filetypes to extract to separate folders
            for name in zip_names:
                if name.split(".")[-1] in files_to_folder:
                    zip_ref.extractall(path=target_path / zip_ref.filename.split(".")[0])
                    # new_path.unlink()
                    break
                else:
                    zip_ref.extractall(target_path)
            logging.debug(f"Successfully extracted {file} to {new_path}")
            zip_ref.close()
            new_path.unlink()

        # Remove unwanted zip and html files
        # clean_up_files(target_path)
        for html_file in target_path.glob("*.html*"):
            if "Table of Contents" in html_file.name:
                clean_up_files(target_path, extensions=[".html"])


def save_html_page(file_name: str, html: str) -> None:
    """
    Saves a html page to given file name from HTML source
    :param file_name: File name to save
    :param html: HTML code
    :return: None
    """
    with open(file_name, "w") as f:
        f.write(html)


def clean_up_files(folder=save_folder, extensions=[".zip"]) -> None:
    """
    Removes files with given provided extensions in provided folder
    :param folder: Folder to clean up files in
    :param extensions: Extensions to look for
    :return:
    """
    files = {p.resolve() for p in pathlib.Path(folder).glob("*") if p.suffix in extensions}
    for file in files:
        file.unlink()


def request_download(url: str) -> None:
    """
    Downloads content from a url
    :param url: Url to download from
    :return: None
    """
    with requests.get(url) as r:
        file_name = url.split("/")[-1]
        r.raise_for_status()
        with open(file_name, "wb") as f:
            f.write(r.content)


def dl_bootcamp_files(bc_url: str = bootcamp_url, bc_password: str = bootcamp_pass,
                      bc_user_name: str = bootcamp_user) -> None:
    """
    Donwloads course content for Python Bootcamp by Yotta consulting
    :param bc_url: Url of page to donwload content from
    :param bc_password: user name for log in
    :param bc_user_name: password for log in
    :return: None
    """
    # Create base folder it if doesn't exist and navigate to it
    create_base_folder(folder=save_folder / "Python coding bootcamp")
    target_path = save_folder / "Python coding bootcamp"

    # Construct url from user name, password and boocamp url
    url = f"https://{bc_user_name}:{bc_password}@{bc_url.replace('https://', '')}"

    # Request url and parse with BeautifulSoup
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "html.parser")
    # Find links on page and extract url
    list_items = soup.find_all("li", class_="list-group")
    links = [item.find("a").get("href") for item in list_items if item.find("a") is not None]
    # Loop over urls and extract those who are datasets or links to files on bootcamp page
    to_download = {}
    for link in links:
        if "yotta" in link:  # Bootcamp files have yotta in link
            to_download[link] = "yotta"
        elif ".zip" in link:  # Datasets are stored as zip and on external links
            to_download[link] = "dataset"

    # Loop over all urls and save to python_bootcamp folder
    for url, source in to_download.items():
        # Check if url is bootcamp url to construct download url with user name and password
        if source == "yotta":
            url_no_method = url.split("//")[-1]
            url = f"https://{bc_user_name}:{bc_password}@{url_no_method}"
            request_download(url)
        else:
            request_download(url)
    # Extract zip files in bootcamp folder
    move_and_extract_files(target_path, source_folder=target_path)


if __name__ == '__main__':
    courses = open_course_list()
    dl_bootcamp_files()

    log_in()
    clean_up_files(save_folder)

    for course in courses:
        clean_up_files()
        course_code = course["code"]
        course_name = course["name"]
        course_url = f"{BASE_URL}{course_code}/home"
        try:
            logging.debug(f"Attempting to get content from {course_name}")
            get_docs_from_course(course_url, course_name)
            logging.debug(f"Finished getting content from {course_name}")
        except Exception as e:
            logging.debug(e)
            # raise e
    driver.quit()  # Explicitly close driver when finished
    clean_up_files(save_folder)
