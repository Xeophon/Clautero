import logging
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import toml
from PyPDF2 import PdfReader
from claude import claude_client
from claude import claude_wrapper
from pyzotero import zotero

# Load the configuration file
config = toml.load("config.toml")

MODEL_NAME = config["general"]["model_name"]
ZOTERO_API_KEY = config["zotero"]["api_key"]
ZOTERO_USER_ID = config["zotero"]["user_id"]
ZOTERO_TODO_TAG_NAME = config["zotero"]["todo_tag_name"]
ZOTERO_SUMMARIZED_TAG_NAME = config["zotero"]["summarized_tag_name"]
ZOTERO_DENY_TAG_NAME = config["zotero"]["deny_tag_name"]
ZOTERO_ERROR_TAG_NAME = config["zotero"]["error_tag_name"]
FILE_BASE_PATH = config["zotero"]["file_path"]
CLAUDE_SESSION_KEY = config["claude"]["session_key"]


def setup_logger():
    """
    Setup Logger

    This method sets up a logger for the "Clautero" application.

    :return: A logger instance configured with console and file handlers.
    """
    # create logger
    logger = logging.getLogger("Clautero")
    logger.setLevel(logging.DEBUG)  # set logger level

    # create console handler and set level to debug
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    # create file handler and set level to debug
    file_handler = logging.FileHandler("application.log")
    file_handler.setLevel(logging.DEBUG)

    # create formatter
    standard_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    # add formatter to handlers
    console_handler.setFormatter(standard_formatter)
    file_handler.setFormatter(standard_formatter)

    # add handlers to logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


zot = zotero.Zotero(ZOTERO_USER_ID, "user", ZOTERO_API_KEY)
claude_client = claude_client.ClaudeClient(CLAUDE_SESSION_KEY)
organizations = claude_client.get_organizations()
claude_obj = claude_wrapper.ClaudeWrapper(claude_client, organizations[0]["uuid"])  # type: ignore
logger = setup_logger()


def unzip_pdf(zip_file_name):
    """
    Unzips a PDF file from the given zip file.

    :param zip_file_name: The name of the zip file containing the PDF.
    :return: The path of the extracted PDF file, stored as a temporary file.
    """
    # Open the zip file in read mode
    with zipfile.ZipFile(zip_file_name, 'r') as zip_ref:
        # Extract the name of the pdf file
        for name in zip_ref.namelist():
            if name.endswith('.pdf'):
                pdf_file_name = name
                break
        else:
            return None
        # Read the pdf file into memory
        pdf_file_data = zip_ref.read(pdf_file_name)
    # Write the pdf file data to a temporary file
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp:
        temp.write(pdf_file_data)
        temp_path = temp.name
    return temp_path


def get_file_path(attachment_key):
    """
    Get the file path for a given attachment.

    :param attachment_key: The key of the attachment.
    :return: The file path for the attachment.
    """
    return Path(f"{FILE_BASE_PATH}\\{attachment_key}.zip")


def key_exists_and_not_none(dictionary: dict, dict_key: Any) -> bool:
    """
    Check if a key exists in a dictionary and its value is not None.

    :param dictionary: The dictionary to check.
    :param dict_key: The key to check in the dictionary.
    :return: True if the key exists and its value is not None, False otherwise.
    """
    return dictionary.get(dict_key) is not None


def write_note(parent_id: str, note_text: str) -> None:
    """
    Write a note to a Zotero item.

    :param parent_id: ID of the parent item to which the note should be attached.
    :param note_text: Text of the note to be added.
    :return: None
    """
    template = zot.item_template("note")
    template["tags"] = [{"tag": MODEL_NAME},
                        {"tag": ZOTERO_SUMMARIZED_TAG_NAME}]
    template["note"] = note_text.replace("\n", "<br>")
    zot.create_items([template], parent_id)


def set_error_tag(item_id: str, tag_name: str) -> None:
    """
    Set the error tag for a given item in Zotero.

    :param item_id: The ID of the item.
    :param tag_name: The name of the error tag to be set.
    :return: None
    """
    logger.info(f"Setting error tag for item {item_id}")
    item_to_update = zot.item(item_id)
    tags = item_to_update["data"]["tags"]
    tags.extend([{"tag": tag_name}])
    item_to_update["data"]["tags"] = tags
    zot.update_item(item_to_update)


def remove_todo_tag(item_id: str) -> None:
    """
    :param item_id: The unique identifier of the item to update.
    :return: None
    """
    logger.info(f"Updating tags for item {item_id}")
    item_to_update = zot.item(item_id)
    tags = item_to_update["data"]["tags"]
    if {"tag": ZOTERO_TODO_TAG_NAME} in tags:
        tags.remove({"tag": ZOTERO_TODO_TAG_NAME})
    elif {"tag": ZOTERO_TODO_TAG_NAME, "type": 1} in tags:
        tags.remove({"tag": ZOTERO_TODO_TAG_NAME, "type": 1})
    item_to_update["data"]["tags"] = tags
    zot.update_item(item_to_update)


def update_tags(item_id):
    """
    Update tags for the specified Zotero item.

    :param item_id: The ID of the item to update.
    """
    logger.info(f"Updating tags for item {item_id}")
    item_to_update = zot.item(item_id)
    tags = item_to_update["data"]["tags"]
    if {"tag": ZOTERO_TODO_TAG_NAME} in tags:
        tags.remove({"tag": ZOTERO_TODO_TAG_NAME})
    elif {"tag": ZOTERO_TODO_TAG_NAME, "type": 1} in tags:
        tags.remove({"tag": ZOTERO_TODO_TAG_NAME, "type": 1})
    tags.extend([{"tag": ZOTERO_SUMMARIZED_TAG_NAME}])
    item_to_update["data"]["tags"] = tags
    zot.update_item(item_to_update)


def get_summary_file(item_name, pdf_file_name):
    """
    :param item_name: The name of the item to be summarized.
    :param pdf_file_name: The name of the PDF file to be attached.
    :return: The summarized text of the item.
    """
    conversation_uuid = claude_obj.start_new_conversation(item_name, "Respond to this message only with 'ok'")
    attachment = claude_obj.get_attachment(pdf_file_name)
    try:
        logger.info(f"Sending {item_name} to Claude for summarization")
        response = claude_obj.send_message(open("prompt.txt", "r").read(), attachments=[attachment],
                                           conversation_uuid=conversation_uuid)["completion"]
        lines = response.splitlines()
        for i, line in enumerate(lines):
            if line.startswith('-'):
                return '\n'.join(lines[i:])
    except Exception as e:
        logger.error(f"Error summarizing {item_name}: {e}")
        return None


if __name__ == "__main__":
    items = zot.top(tag=[ZOTERO_TODO_TAG_NAME, f"-{ZOTERO_ERROR_TAG_NAME}", f"-{ZOTERO_DENY_TAG_NAME}"], limit=50)
    logger.info(f"Found {len(items)} items to summarize")
    for item in items:
        key = item["data"]["key"]
        pdf_temp_path = None
        if not key_exists_and_not_none(item["data"], "title"):
            logger.warning(f"Skipping item {key} because it has no title")
            set_error_tag(key, ZOTERO_ERROR_TAG_NAME)
            continue
        logger.info(f"Searching attachments for {item['data']['title']} [{key}]")
        zot_children = zot.children(key)
        pdf_items = [child for child in zot_children if child.get('data', {}).get('contentType') == 'application/pdf']
        first_pdf_item = pdf_items[0] if pdf_items else None
        if first_pdf_item is None:
            logger.error(f"No PDF attachment found for item {key}, skipping.")
            set_error_tag(key, ZOTERO_DENY_TAG_NAME)
            continue

        children_key = first_pdf_item["key"]
        pdf_temp_path = unzip_pdf(get_file_path(children_key))

        if pdf_temp_path is None:
            logger.error(f"Could not find a PDF for item {key} in Koofr, skipping.")
            set_error_tag(key, ZOTERO_ERROR_TAG_NAME)
            continue
        if not 5 <= len(PdfReader(pdf_temp_path).pages) <= 60:
            logger.error(f"PDF length is out of bounds, skipping.")
            set_error_tag(key, ZOTERO_DENY_TAG_NAME)
            remove_todo_tag(key)
            continue

        summary = get_summary_file(str(pdf_temp_path), pdf_temp_path)
        text = f"Summary\n\n{summary}"
        if summary is None:
            logger.error(f"Could not summarize item {key}, skipping.")
            set_error_tag(key, ZOTERO_ERROR_TAG_NAME)
            continue
        write_note(key, text)
        update_tags(key)
