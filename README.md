# Clautero CLI

Small script to auto-summarize new papers in the Zotero library. 

## Setup

1. Edit your research topics / topics which Claude should not dive further into in `prompt.txt`
2. `pip install -r requirements.txt`
3. Get your session key from Claude.ai (it is a cookie value)
4. Rename `config.example.toml` to `config.toml` and add the missing values.
5. `python main.py`

## Config values

- `[zotero]user_id` is the user ID of your Zotero Account
- `[zotero]api_key` is the API key of the Zotero Web API. Needs both read + write access
- `[zotero]todo_tag_name` is the name of the tag to add summaries to. Works great together with [zotero-tag](https://github.com/windingwind/zotero-tag) to add tags automatically
- `[zotero]summarized_tag_name`, `[zotero]error_tag_name` get automatically added after an (un)successful summary occured
- `[zotero]deny_tag_name`  has to be set manually for items which should not be summarized (e.g. own, unpublished papers)
- `[zotero]file_path` is the path to the attachments of the zotero library (-> should contain a lot of .zip files with IDs) to get the paper
  - **Important**: When using Linux/macOS, change the line separator in [L100](https://github.com/Xeophon/Clautero/blob/9c89c20c97a574760526192464bbb5111edcc55a/main.py#L100)
