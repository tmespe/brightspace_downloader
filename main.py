# Downloads course content from brightspace and saves to disk

import json
import logging
import os
import pathlib
import zipfile
import argparse
import sys
import requests

from time import sleep
from typing import Union, Optional

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import NoAlertPresentException, NoSuchElementException
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
save_folder = args.directory or save_folder  # Use save folder from argument if set, else save to default
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
    driver.switch_to.frame(frame_xpath[0])
    driver.implicitly_wait(10)

    # Content is divided into units. Get all units using class name
    all_units = driver.find_elements_by_class_name("unit")
    # Make sure units exist so only courses with content have folders created
    if all_units:
        # Create course folder and switch to it
        pathlib.Path(course_name).mkdir(parents=True, exist_ok=True)
        os.chdir(course_name)

        # Loop over all units on the content iframe and click download button and save
        for unit in all_units:
            unit_name = unit.text.split("\n")[0]

            pathlib.Path(unit.text).mkdir(parents=True, exist_ok=True)
            unit.click()
            driver.implicitly_wait(2)  # Wait to make sure unit is loaded before clicking download
            try:
                download_url = driver.find_element_by_class_name("download-content-button")
                download_url.click()
            except NoSuchElementException as e:
                logging.error(e)
                continue
            logging.debug(f"Downloading {unit_name}")
            # logging.debug("%s downloaded", unit_name)
            sleep(60)
            logging.debug(f"Downloaded {unit_name}")
            move_and_extract_files(pathlib.Path(unit_name))
    else:
        pass


def move_and_extract_files(destination_folder, sourcefolder=save_folder, extension="*.zip*") -> None:
    """
    Moves and extracts files with a given extension from source folder to destination folder
    :param destination_folder: Folder to move files to
    :param sourcefolder: Folder to move files from
    :param extension: Extension of files to move
    """
    files_to_folder = ["ipynb", "csv", "txt", "py"]  # Filetypes to extract to separate folders
    for file in pathlib.Path(sourcefolder).glob(extension):
        target_path = destination_folder
        new_path = file.rename(target_path.joinpath(file.name))
        logging.debug(f"Extracting {file} form {target_path} to {new_path}")
        print(f"Extracting {file} form {target_path} to {new_path}")

        zip_ref = zipfile.ZipFile(new_path)
        zip_names = zip_ref.namelist()
        if len(zip_names) > 5:  # Don't extract zip files with too many items
            continue
        # Loop over files in zip to check for filetypes to extract to separate folders
        for name in zip_names:
            if name.split(".")[-1] in files_to_folder:
                zip_ref.extractall(path=target_path / zip_ref.filename.split(".")[0])
                #new_path.unlink()
                break
            else:
                zip_ref.extractall(target_path)
        logging.debug(f"Successfully extracted {file} to {new_path}")
        zip_ref.close()

        # Remove unwanted zip and html files
        new_path.unlink()
        for html_file in target_path.glob("*.html*"):
            html_file.unlink()


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
    create_base_folder(folder=save_folder / "python_bootcamp")
    # Construct url from user name, password and boocamp url
    url = f"https://{bc_user_name}:{bc_password}@{bc_url}"

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
        elif ".zip" in link:  # Datasets are stored as zip
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
    move_and_extract_files(save_folder/"python_bootcamp", sourcefolder=save_folder/"python_bootcamp")


if __name__ == '__main__':
    courses = open_course_list()
    log_in()

    for course in courses:
        course_code = course["code"]
        course_name = course["name"]
        course_url = f"{BASE_URL}/{course_code}/home"
        try:
            logging.debug(f"Attempting to get content from {course_name}")
            get_docs_from_course(course_url, course_name)
            logging.debug(f"Finished getting content from {course_name}")
        except Exception as e:
            logging.debug(e)
    driver.quit()  # Explicitly close driver when finished
    dl_bootcamp_files()

