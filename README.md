# Clautero

Small script to auto-summarize new papers in the Zotero library.

The script works by looking at tags of top-level items (
see [Config Values](https://github.com/Xeophon/Clautero#config-values)) and then sending the PDF to Claude and asking
for a summary in the style of [the prompt](https://github.com/Xeophon/Clautero/blob/main/prompt.txt). After getting a
response, it attaches the summary as a note to the top-level item and then updates the tags.

> [!WARNING]
> Large Language Models are prone to hallucinations and the generated summaries may be inaccurate. Do not rely on them
> as a source of truth.

## Setup

1. Edit the prompt from `prompt.txt`
2. Edit the config (`config.example.ini`) and rename it to `config.ini`
3. Build the docker container (`docker build -t clautero`)
4. Run the container (`docker run -d -p 5000:5000 -v /mnt/your/local/path/to/zotero/attachments:/app/zotero`)

## Config Values

- `[claude]api_key` is your Anthropic API key
- `[zotero]user_id` is the user ID of your Zotero Account
- `[zotero]file_path` is the path to your Zotero attachments
- `[zotero]api_key` is the API key of the Zotero Web API. Needs both read + write access
- `[zotero]todo_tag_name` is the name of the tag to add summaries to. Works great together with [zotero-tag](https://github.com/windingwind/zotero-tag) to add tags automatically
- `[zotero]summarized_tag_name`, `[zotero]error_tag_name` get automatically added after an (un)successful summary occured
- `[zotero]deny_tag_name` has to be set manually for items (in Zotero) which should not be summarized (e.g. own, unpublished papers)

## Usage

The Docker container exposes a web server with the following services:

- `GET /ping/`: Returns `{"status": "Server is up and running!"}` if the server is running
- `GET /add_missing_tags/`: Adds `[zotero]todo_tag_name` to items which have no Clautero-related tags (i.e. those in
  the `config.ini`). Can be used instead of using [zotero-tag](https://github.com/windingwind/zotero-tag).
- `GET /summarize/`: Starts the summarization of all papers with `[zotero]todo_tag_name`. The endpoint immediately
  returns a response and continues in the background as the summarization may take a long time.

## Possible Failures
- Items which have no attachments will not be summarized
- Items with PDFs which are too small (<5 pages) or too large (>60 pages) will not be summarized
- If the PDF has text which is hard to extract (i.e. old papers/books) will result in bad summaries
- Sometimes, Claude wants to summarize the prompt. In my tests, this usually happens if the text is hard to extract
- Images in PDFs cannot be summarized