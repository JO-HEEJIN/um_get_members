import time
import json
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
from bs4 import BeautifulSoup

base_url = "https://example.com"  # Change to your target URL
ajax_url = f"{base_url}/wp-admin/admin-ajax.php"

def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def analyze_members_page(driver):
    print("Analyzing member directory page...")
    driver.get(f"{base_url}/members/")
    time.sleep(3)
    driver.save_screenshot("members_page_initial.png")
    print("Initial page screenshot saved as 'members_page_initial.png'")
    
    print("Analyzing HTML structure...")
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    directory_elem = soup.select_one('.um-directory')
    if directory_elem:
        print("Directory element found!")
        for attr in directory_elem.attrs:
            if attr.startswith('data-'):
                print(f"  {attr}: {directory_elem[attr]}")
    else:
        print("Directory element not found. Searching for all 'data-' attributes:")
        for elem in soup.select('[data-]'):
            for attr in elem.attrs:
                if attr.startswith('data-'):
                    print(f"  {elem.name}.{attr}: {elem[attr]}")
    
    js_data = driver.execute_script("""
        var data = {
            title: document.title,
            url: window.location.href,
            um_scripts: (typeof um_scripts !== 'undefined') ? JSON.stringify(um_scripts) : null,
            wp_ajax_url: (typeof ajaxurl !== 'undefined') ? ajaxurl : null,
            directory_elements: []
        };
        
        var directories = document.querySelectorAll('.um-directory, [class*="um-"], [id*="um-"]');
        for(var i = 0; i < directories.length; i++) {
            var elem = directories[i];
            var elem_data = {
                tag: elem.tagName,
                id: elem.id,
                class: elem.className,
                data: {}
            };
            
            var attributes = elem.attributes;
            for(var j = 0; j < attributes.length; j++) {
                var attr = attributes[j];
                if(attr.name.startsWith('data-')) {
                    elem_data.data[attr.name] = attr.value;
                }
            }
            
            data.directory_elements.push(elem_data);
        }
        
        data.network_info = {
            loadMoreUrl: null,
            possibleActions: ['um_get_members', 'um_filter_members', 'um_load_more_members']
        };
        
        return data;
    """)
    
    print("\nData extracted from JavaScript:")
    
    if js_data['um_scripts']:
        try:
            um_scripts = json.loads(js_data['um_scripts'])
            print("  um_scripts.nonce:", um_scripts.get('nonce', 'None'))
        except:
            print("  Failed to parse um_scripts")
    
    print("  wp_ajax_url:", js_data['wp_ajax_url'] or 'None')
    
    directory_data = {}
    for i, elem in enumerate(js_data['directory_elements']):
        if elem['data']:
            print(f"\n  Directory element #{i+1}: {elem['tag']} (id: {elem['id']}, class: {elem['class']})")
            for key, value in elem['data'].items():
                print(f"    {key}: {value}")
                
                if key == 'data-hash':
                    directory_data['hash'] = value
                elif key == 'data-directory-id' or key == 'data-id':
                    directory_data['directory_id'] = value
                elif 'page' in key:
                    directory_data['page'] = value
    
    print("\nAnalyzing AJAX requests through page interaction...")
    
    load_more_btn = None
    try:
        load_more_btn = driver.find_element(By.CSS_SELECTOR, '.um-load-more')
        print("Load more button found!")
        
        for attr in ['data-pages', 'data-page', 'data-load']:
            try:
                value = load_more_btn.get_attribute(attr)
                if value:
                    print(f"  {attr}: {value}")
                    directory_data[attr.replace('data-', '')] = value
            except:
                pass
    except:
        print("Load more button not found")
    
    directory_data['nonce'] = extract_nonce(driver)
    
    cookies = driver.get_cookies()
    cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
    
    print("\nExtracted parameters:")
    for k, v in directory_data.items():
        print(f"  {k}: {v}")
    
    if 'directory_id' not in directory_data or not directory_data['directory_id']:
        print("\nWarning: directory_id not found, setting default value")
        directory_data['directory_id'] = 'default'
    
    return directory_data, cookie_dict

def extract_nonce(driver):
    nonce = driver.execute_script("return (typeof um_scripts !== 'undefined') ? um_scripts.nonce : null;")
    if nonce:
        print(f"Nonce found in um_scripts: {nonce}")
        return nonce
    
    source = driver.page_source
    nonce_patterns = [
        r'um_scripts[\s\S]*?nonce[\s\S]*?["\']([^"\']+)["\']',
        r'nonce["\']?\s*:\s*["\']([^"\']+)["\']',
        r'_wpnonce["\']?\s*:\s*["\']([^"\']+)["\']',
        r'name="_wpnonce"\s+value="([^"]+)"'
    ]
    
    for pattern in nonce_patterns:
        match = re.search(pattern, source)
        if match:
            nonce = match.group(1)
            print(f"Nonce found using regex: {nonce}")
            return nonce
    
    soup = BeautifulSoup(source, 'html.parser')
    nonce_inputs = soup.select('input[name="_wpnonce"], input[name="nonce"], input[name="um_nonce"]')
    for input_field in nonce_inputs:
        nonce = input_field.get('value')
        if nonce:
            print(f"Nonce found in input field: {nonce}")
            return nonce
    
    print("No nonce found")
    return ""

def get_members_data(params, cookies):
    all_members = []
    page = 1
    max_pages = 10
    
    if 'pages' in params and params['pages']:
        try:
            max_pages = int(params['pages'])
        except:
            pass
    
    print(f"Starting to collect member data via AJAX (max {max_pages} pages)...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': f"{base_url}/members/",
        'Origin': base_url
    }
    
    cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
    if cookie_str:
        headers['Cookie'] = cookie_str
    
    actions = ['um_get_members', 'um_load_more_members']
    success = False
    
    for action in actions:
        if success:
            break
        
        print(f"\nTrying action '{action}'...")
        page = 1
        
        while page <= max_pages:
            print(f"Requesting page {page}/{max_pages}...")
            
            data = {
                'action': action,
                'page': str(page),
                'directory_id': params.get('directory_id', 'default'),
                'hash': params.get('hash', ''),
                'nonce': params.get('nonce', '')
            }
            
            if action == 'um_get_members':
                data['members_page'] = '1'
            
            try:
                print(f"Request URL: {ajax_url}")
                print(f"Request headers: {headers}")
                print(f"Request data: {data}")
                
                response = requests.post(ajax_url, headers=headers, data=data)
                
                print(f"Response status code: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        json_data = response.json()
                        print(f"Response JSON: {json.dumps(json_data)[:200]}..." if len(json.dumps(json_data)) > 200 else json.dumps(json_data))
                        
                        if json_data.get('success') == True:
                            success = True
                            
                            if 'users' in json_data:
                                members = json_data['users']
                            elif 'data' in json_data and 'users' in json_data['data']:
                                members = json_data['data']['users']
                            else:
                                print(f"No member data found in response.")
                                if 'html' in json_data:
                                    print("Trying to extract member data from HTML response...")
                                    members = extract_member_data_from_html(json_data['html'])
                                else:
                                    members = []
                            
                            if not members:
                                print(f"No member data on page {page}.")
                                break
                            
                            all_members.extend(members)
                            print(f"Retrieved {len(members)} members from page {page}.")
                            
                            if 'pagination' in json_data and 'pages' in json_data['pagination']:
                                max_pages = int(json_data['pagination']['pages'])
                                print(f"Pagination info: {max_pages} total pages")
                            
                            if page >= max_pages:
                                print("Reached last page.")
                                break
                        else:
                            error_msg = json_data.get('data', 'Unknown error')
                            print(f"Request failed: {error_msg}")
                            
                            if "invalid nonce" in str(error_msg).lower():
                                print("Nonce is invalid.")
                                break
                            
                    except json.JSONDecodeError:
                        print("Response is not in JSON format.")
                        print(f"Response text: {response.text[:200]}..." if len(response.text) > 200 else response.text)
                        
                        if '<div class="um-member"' in response.text:
                            print("Trying to extract member data from HTML response...")
                            members = extract_member_data_from_html(response.text)
                            if members:
                                success = True
                                all_members.extend(members)
                                print(f"Extracted {len(members)} members from HTML.")
                        
                        if not success:
                            break
                else:
                    print(f"Request failed: status code {response.status_code}")
                    print(f"Response text: {response.text[:200]}..." if len(response.text) > 200 else response.text)
                    break
                    
                page += 1
                time.sleep(2)
                
            except Exception as e:
                print(f"Error during request: {str(e)}")
                break
    
    return all_members

def extract_member_data_from_html(html_content):
    members = []
    soup = BeautifulSoup(html_content, 'html.parser')
    
    member_elements = soup.select('.um-member')
    
    if not member_elements:
        print("No members found with basic selector. Trying alternative selectors...")
        member_elements = soup.select('[class*="um-member"]')
    
    print(f"Found {len(member_elements)} member elements in HTML.")
    
    for elem in member_elements:
        try:
            member = {}
            
            member_id = elem.get('data-member-id', '')
            if not member_id:
                profile_link = elem.select_one('a[href*="/user/"]')
                if profile_link:
                    url = profile_link.get('href', '')
                    match = re.search(r'/user/([^/]+)', url)
                    if match:
                        member_id = match.group(1)
            
            member['id'] = member_id or f"unknown-{len(members)}"
            
            name_selectors = ['.um-member-name', '.um-member-name a', '[class*="name"]', 'h3', '.um-member-card-header']
            for selector in name_selectors:
                name_elem = elem.select_one(selector)
                if name_elem:
                    member['name'] = name_elem.get_text(strip=True)
                    break
            
            profile_link = elem.select_one('a[href*="/user/"]') or elem.select_one('a')
            if profile_link:
                member['profile_url'] = profile_link.get('href', '')
            
            meta_selectors = [
                '.um-member-meta-data', 
                '.um-member-meta', 
                '[class*="meta"]', 
                '.um-member-card-content',
                '.um-member-card-footer'
            ]
            
            for meta_selector in meta_selectors:
                meta_elements = elem.select(meta_selector)
                if meta_elements:
                    for meta in meta_elements:
                        meta_name_elem = meta.select_one('.um-meta-name') or meta.select_one('strong') or meta.select_one('label')
                        meta_value_elem = meta.select_one('.um-meta-value') or meta.select_one('span:not(.um-meta-name)') or meta.select_one('p')
                        
                        if meta_name_elem and meta_value_elem:
                            field_name = meta_name_elem.get_text(strip=True).lower().replace(' ', '_')
                            member[field_name] = meta_value_elem.get_text(strip=True)
                        elif not meta_name_elem and meta_value_elem:
                            class_name = meta.get('class', ['unknown'])
                            field_name = class_name[0].lower().replace('um-', '').replace('-', '_') if class_name else 'info'
                            member[field_name] = meta_value_elem.get_text(strip=True)
                        elif meta.get_text(strip=True):
                            text = meta.get_text(strip=True)
                            if ':' in text:
                                parts = text.split(':', 1)
                                field_name = parts[0].strip().lower().replace(' ', '_')
                                member[field_name] = parts[1].strip()
                            else:
                                member[f'info_{len(member)}'] = text
            
            role_elem = elem.select_one('.um-member-role') or elem.select_one('[class*="role"]')
            if role_elem:
                member['role'] = role_elem.get_text(strip=True)
            
            if elem.select_one('.um-online-status.online'):
                member['online_status'] = 'online'
                
            img_elem = elem.select_one('img.um-avatar') or elem.select_one('img')
            if img_elem:
                member['avatar_url'] = img_elem.get('src', '')
                
            members.append(member)
            
        except Exception as e:
            print(f"Error processing member element: {str(e)}")
            continue
    
    return members

def try_login(driver, username, password):
    print(f"Attempting to log in with account '{username}'...")
    
    login_url = f"{base_url}/wp-login.php"
    
    login_page = driver.get(login_url)
    login_soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    hidden_fields = {}
    for input_tag in login_soup.find_all('input', type='hidden'):
        hidden_fields[input_tag.get('name')] = input_tag.get('value')
    
    login_data = {
        "log": username,
        "pwd": password,
        "wp-submit": "Log In",
        "redirect_to": f"{base_url}/wp-admin/",
        "testcookie": "1"
    }
    
    login_data.update(hidden_fields)
    
    try:
        username_field = driver.find_element(By.ID, "user_login")
        password_field = driver.find_element(By.ID, "user_pass")
        submit_button = driver.find_element(By.ID, "wp-submit")
        
        username_field.send_keys(username)
        password_field.send_keys(password)
        submit_button.click()
        
        WebDriverWait(driver, 5).until(
            lambda d: "wp-admin" in d.current_url or "login" in d.current_url
        )
        
        if "wp-admin" in driver.current_url:
            print("Login successful!")
            return True
        else:
            print("Login failed: incorrect credentials.")
            return False
    except Exception as e:
        print(f"Error during login: {str(e)}")
        return False

def save_data(members):
    if not members:
        print("No member data to save.")
        return
        
    with open("members_data.json", "w", encoding="utf-8") as f:
        json.dump(members, f, indent=2, ensure_ascii=False)
        
    print(f"Total of {len(members)} members saved to 'members_data.json'.")
    
    schema = {
        "version": "Contact Form 7 SWV Schema 2024-10",
        "locale": "en_US",
        "rules": []
    }
    
    for member in members:
        member_id = member.get("id", "unknown")
        
        for field_name, value in member.items():
            if field_name in ["id", "profile_url"]:
                continue
            
            form_field_name = f"member-{member_id}-{field_name}"
            
            schema["rules"].append({
                "rule": "required",
                "field": form_field_name,
                "error": f"Please fill in the {field_name.replace('_', ' ')} field."
            })
            
            schema["rules"].append({
                "rule": "maxlength",
                "field": form_field_name,
                "threshold": 400,
                "error": f"The {field_name.replace('_', ' ')} field is too long."
            })
            
            if "email" in field_name:
                schema["rules"].append({
                    "rule": "email",
                    "field": form_field_name,
                    "error": "Please enter a valid email address."
                })
    
    with open("members_schema.json", "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
        
    print(f"Contact Form 7 SWV Schema saved to 'members_schema.json'.")

def main():
    driver = None
    try:
        print("Initializing Selenium WebDriver...")
        driver = setup_driver()
        
        print("Analyzing member directory page...")
        params, cookies = analyze_members_page(driver)
        
        if 'hash' in params and params['hash']:
            params['directory_id'] = params['hash']
            print(f"Setting directory_id to hash value: {params['directory_id']}")
        
        print("Extracting member data directly from the page...")
        initial_members = extract_member_data_from_html(driver.page_source)
        print(f"Extracted {len(initial_members)} members from HTML.")
        
        driver.quit()
        driver = None
        
        ajax_members = get_members_data(params, cookies)
        
        all_members = initial_members.copy()
        
        if ajax_members:
            existing_ids = {member['id'] for member in all_members if 'id' in member}
            for member in ajax_members:
                if 'id' in member and member['id'] not in existing_ids:
                    all_members.append(member)
                    existing_ids.add(member['id'])
        
        print(f"Total {len(all_members)} members collected.")
        
        save_data(all_members)
        
    except Exception as e:
        print(f"Error during execution: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            driver.quit()
            print("WebDriver terminated")

if __name__ == "__main__":
    main()
