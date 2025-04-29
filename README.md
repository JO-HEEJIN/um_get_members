# um_get_members
**extracting member information from websites without permission** 
# Ultimate Member Data Scraper

This tool is a Python script designed to extract and analyze member information from websites using the Ultimate Member WordPress plugin. The script collects member data from web pages, saves it in JSON format, and converts it to Contact Form 7 SWV Schema format.

## Demo

![Ultimate Member Directory Screenshot](https://github.com/um_get_members/members_page_initial.png)

*Screenshot of Ultimate Member directory page captured during data extraction*

## Features

- Extract member data from Ultimate Member directory pages
- Collect data through HTML analysis and AJAX requests
- Save extracted data as JSON
- Convert data to Contact Form 7 SWV Schema format
- Robust parsing capabilities for various website structures

## Installation

### Requirements

- Python 3.7 or higher
- pip (Python package manager)
- Recommended to use a virtual environment

### Installation Steps

1. Clone or download the repository

```bash
git clone https://github.com/yourusername/ultimate-member-scraper.git
cd ultimate-member-scraper
```

2. Create and activate a virtual environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

3. Install required packages

```bash
pip install -r requirements.txt
```

Or install packages directly:

```bash
pip install requests beautifulsoup4 selenium webdriver-manager lxml
```

## Usage

### Basic Usage

1. Run the script:

```bash
python um_scraper.py
```

2. Set the target URL:

Change the `base_url` variable in the script to your target website URL:

```python
base_url = "https://example.com"  # Change to your target URL
```

### Advanced Usage

#### Setting Login Credentials

If login is required, you can set username and password:

```python
# Provide user credentials when calling the login function
login_success = try_login(driver, "username", "password")
```

#### Manually Specify Nonce Value

To directly specify a nonce value:

```python
# Set nonce value directly
params['nonce'] = "your_nonce_value"
```

## Main Files

- `um_scraper.py`: Main script file
- `requirements.txt`: List of required packages
- `README.md`: Usage guide

## How It Works

1. **Initialization**: Set up Selenium WebDriver and access the member directory page.
2. **Page Analysis**: Analyze HTML structure to extract necessary parameters (directory_id, hash, nonce, etc.).
3. **Data Collection**:
   - Extract member data directly from HTML
   - Try to get additional member data through AJAX requests
4. **Data Processing**: Process the extracted member data and remove duplicates.
5. **Data Storage**: Save results as JSON files and convert to SWV Schema format if needed.

## Output Example

The script generates two output files:

1. `members_data.json` - Contains the raw member data:

```json
[
  {
    "id": "user123",
    "name": "John Doe",
    "profile_url": "https://example.com/user/john-doe/",
    "role": "Member",
    "email": "john@example.com"
  },
  ...
]
```

2. `members_schema.json` - Contains the Contact Form 7 SWV Schema format:

```json
{
  "version": "Contact Form 7 SWV Schema 2024-10",
  "locale": "en_US",
  "rules": [
    {
      "rule": "required",
      "field": "member-user123-name",
      "error": "Please fill in the name field."
    },
    ...
  ]
}
```

## Troubleshooting

### "Invalid Member Directory Data" Error

This error occurs when the `directory_id` is incorrectly set. You can solve it by:

1. Using the `hash` value as the `directory_id`:

```python
params['directory_id'] = params['hash']
```

2. Finding the correct `data-directory-id` or `data-id` value in the page source.

### Nonce Error

If the nonce value is invalid or expired:

1. Visit the page directly to extract the latest nonce value.
2. Modify the script to use the new nonce value.

### Member Data Not Extracted

The HTML structure might be different than expected:

1. Use browser developer tools to check the actual HTML structure of member elements.
2. Adjust the CSS selectors in the `extract_member_data_from_html` function to match the site structure.

## Limitations

- This script should only be used for educational and research purposes.
- Respect website terms of service.
- Comply with privacy laws when collecting user data.
- Avoid sending excessive requests to websites.

## License

MIT License

## Contributing

Issues and Pull Requests are welcome. Please create an issue first to discuss any major changes before applying them.
