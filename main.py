# Downloads course content from brightspace and saves to disk

import json
import logging
import os
import pathlib
import zipfile
import argparse
import sys

from time import sleep
from typing import Union, Optional

from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import NoAlertPresentException
from selenium.webdriver.firefox.options import Options

# Set up logging
logging.basicConfig(level=logging.DEBUG, filename='downloads.log', filemode='w',
                    format='%(asctime)s %(name)s - %(levelname)s - %(message)s')
logging.getLogger().addHandler(logging.StreamHandler())

# Load environment, urls and save folders
load_dotenv()
LOGIN_URL = "https://emlyon.brightspace.com/"
BASE_URL = "https://emlyon.brightspace.com/d2l/le/content/"
save_folder = pathlib.Path.home() / "Documents/Em-lyon/brightspace"  # Save to user Documents folder
user = os.getenv("USER_NAME")
password = os.getenv("PASSWORD")

# Argparse
my_parser = argparse.ArgumentParser(description='Download course contents from brightspace')

my_parser.add_argument("-d",
                       "--directory",
                       metavar="arg_directory",
                       type=str,
                       help="name of text arg_file to search")

args = my_parser.parse_args()
save_folder = args.directory or save_folder
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
                  "url": "https://emlyon.brightspace.com/d2l/le/lessons/210338/units/742721",
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
    # Select html xpath for username, password and sign in button
    if not user or not password:
        sys.exit("No username or password provided. Did you create a .env file with USER_NAME and PASSWORD?")
    user_xpath = '//*[@id="userNameInput"]'
    password_xpath = '//*[@id="passwordInput"]'
    sign_in_button = '//*[@id="submitButton"]'

    driver.get(LOGIN_URL)
    # Handle cases where on local network and an alert login pop up displays
    if not check_if_alert():
        # Find username, pasword and sign in elements and send keys for log in
        user_element = driver.find_element_by_xpath(user_xpath)
        password_element = driver.find_element_by_xpath(password_xpath)
        sign_in = driver.find_element_by_xpath(sign_in_button)
        user_element.send_keys(user)
        password_element.send_keys(password)
        sign_in.click()


def get_docs_from_course(url: str, course_name: str) -> None:
    """
    Gets course documents from brightspace learning platform and saves them to a course unit folder within
    the course name folder.
    :param url: Url of course content
    :param course_name: Name of course
    """
    # Make sure firefox profile download folder exists and is set
    pathlib.Path(save_folder).mkdir(parents=True, exist_ok=True)
    os.chdir(save_folder)

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

        # Loop over all units on the content iframe and select download button and save
        for unit in all_units:
            unit_name = unit.text.split("\n")[0]

            pathlib.Path(unit.text).mkdir(parents=True, exist_ok=True)
            unit.click()
            driver.implicitly_wait(2)
            download_url = driver.find_element_by_class_name("download-content-button")
            download_url.click()
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
    for file in pathlib.Path(sourcefolder).glob(extension):
        target_path = destination_folder
        new_path = file.rename(target_path.joinpath(file.name))
        logging.debug(f"Extracting {file} form {target_path} to {new_path}")
        print(f"Extracting {file} form {target_path} to {new_path}")
        zip_ref = zipfile.ZipFile(new_path)
        zip_ref.extractall(target_path)
        logging.debug(f"Successfully extracted {file} to {new_path}")
        zip_ref.close()

        # Remove unwanted zip and html files
        new_path.unlink()
        for html_file in target_path.glob("*.html*"):
            html_file.unlink()


if __name__ == '__main__':
    log_in()
    courses = open_course_list()

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
