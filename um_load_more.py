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

# 기본 설정
base_url = "https://niaverse.com"
ajax_url = f"{base_url}/wp-admin/admin-ajax.php"

def setup_driver():
    """Selenium WebDriver 설정"""
    options = webdriver.ChromeOptions()
    options.add_argument("--window-size=1920,1080")
    
    # 브라우저 감지 방지 옵션
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    # UserAgent 설정
    options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # WebDriver 초기화 및 반환
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    # JavaScript 감지 우회
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

def analyze_members_page(driver):
    """회원 페이지 분석 및 모든 가능한 파라미터 추출"""
    print("회원 디렉토리 페이지 분석 중...")
    
    # 회원 디렉토리 페이지 방문
    driver.get(f"{base_url}/members/")
    time.sleep(3)  # 페이지 로딩 대기
    
    # 페이지 스크린샷 저장 (디버깅용)
    driver.save_screenshot("members_page_initial.png")
    print("초기 페이지 스크린샷이 'members_page_initial.png'로 저장되었습니다.")
    
    # 1. HTML 소스에서 필요한 요소 찾기
    print("HTML 구조 분석 중...")
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    # 모든 중요한 데이터 속성 출력
    directory_elem = soup.select_one('.um-directory')
    if directory_elem:
        print("디렉토리 요소 찾음!")
        for attr in directory_elem.attrs:
            if attr.startswith('data-'):
                print(f"  {attr}: {directory_elem[attr]}")
    else:
        print("디렉토리 요소를 찾을 수 없음. 대신 모든 'data-' 속성 검색:")
        for elem in soup.select('[data-]'):
            for attr in elem.attrs:
                if attr.startswith('data-'):
                    print(f"  {elem.name}.{attr}: {elem[attr]}")
    
    # 2. JavaScript를 통해 모든 가능한 파라미터와 전역 변수 추출
    js_data = driver.execute_script("""
        var data = {
            // 페이지 정보
            title: document.title,
            url: window.location.href,
            
            // um_scripts 객체 검색
            um_scripts: (typeof um_scripts !== 'undefined') ? JSON.stringify(um_scripts) : null,
            
            // wp 객체 확인
            wp_ajax_url: (typeof ajaxurl !== 'undefined') ? ajaxurl : null,
            
            // 디렉토리 요소 검색
            directory_elements: []
        };
        
        // 모든 가능한 디렉토리 요소 찾기
        var directories = document.querySelectorAll('.um-directory, [class*="um-"], [id*="um-"]');
        for(var i = 0; i < directories.length; i++) {
            var elem = directories[i];
            var elem_data = {
                tag: elem.tagName,
                id: elem.id,
                class: elem.className,
                data: {}
            };
            
            // 모든 data- 속성 수집
            var attributes = elem.attributes;
            for(var j = 0; j < attributes.length; j++) {
                var attr = attributes[j];
                if(attr.name.startsWith('data-')) {
                    elem_data.data[attr.name] = attr.value;
                }
            }
            
            data.directory_elements.push(elem_data);
        }
        
        // 네트워크 분석
        data.network_info = {
            loadMoreUrl: null,
            possibleActions: ['um_get_members', 'um_filter_members', 'um_load_more_members']
        };
        
        return data;
    """)
    
    print("\nJavaScript에서 추출한 데이터:")
    
    # um_scripts 데이터 파싱
    if js_data['um_scripts']:
        try:
            um_scripts = json.loads(js_data['um_scripts'])
            print("  um_scripts.nonce:", um_scripts.get('nonce', '없음'))
        except:
            print("  um_scripts 파싱 실패")
    
    # Ajax URL 확인
    print("  wp_ajax_url:", js_data['wp_ajax_url'] or '없음')
    
    # 디렉토리 요소 탐색
    directory_data = {}
    for i, elem in enumerate(js_data['directory_elements']):
        if elem['data']:
            print(f"\n  디렉토리 요소 #{i+1}: {elem['tag']} (id: {elem['id']}, class: {elem['class']})")
            for key, value in elem['data'].items():
                print(f"    {key}: {value}")
                
                # 중요한 데이터 저장
                if key == 'data-hash':
                    directory_data['hash'] = value
                elif key == 'data-directory-id' or key == 'data-id':
                    directory_data['directory_id'] = value
                elif 'page' in key:
                    directory_data['page'] = value
    
    # 3. 페이지 상호작용을 통한 AJAX 요청 분석
    print("\n페이지 상호작용을 통한 AJAX 요청 분석 중...")
    
    # 더 보기 버튼 찾기
    load_more_btn = None
    try:
        load_more_btn = driver.find_element(By.CSS_SELECTOR, '.um-load-more')
        print("더 보기 버튼 찾음!")
        
        # 버튼 속성 읽기
        for attr in ['data-pages', 'data-page', 'data-load']:
            try:
                value = load_more_btn.get_attribute(attr)
                if value:
                    print(f"  {attr}: {value}")
                    directory_data[attr.replace('data-', '')] = value
            except:
                pass
    except:
        print("더 보기 버튼을 찾을 수 없음")
    
    # 4. Nonce 추출
    directory_data['nonce'] = extract_nonce(driver)
    
    # 5. 쿠키 가져오기
    cookies = driver.get_cookies()
    cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
    
    # 6. 결과 요약
    print("\n추출된 파라미터:")
    for k, v in directory_data.items():
        print(f"  {k}: {v}")
    
    # 디렉토리 ID가 없으면 기본값 설정
    if 'directory_id' not in directory_data or not directory_data['directory_id']:
        print("\n경고: directory_id를 찾을 수 없어 기본값 설정")
        directory_data['directory_id'] = 'default'
    
    return directory_data, cookie_dict

def extract_nonce(driver):
    """여러 방법으로 nonce 값 추출"""
    # 1. um_scripts에서 추출
    nonce = driver.execute_script("return (typeof um_scripts !== 'undefined') ? um_scripts.nonce : null;")
    if nonce:
        print(f"um_scripts에서 nonce 찾음: {nonce}")
        return nonce
    
    # 2. 소스 코드에서 정규식으로 찾기
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
            print(f"정규식으로 nonce 찾음: {nonce}")
            return nonce
    
    # 3. hidden input 필드에서 찾기
    soup = BeautifulSoup(source, 'html.parser')
    nonce_inputs = soup.select('input[name="_wpnonce"], input[name="nonce"], input[name="um_nonce"]')
    for input_field in nonce_inputs:
        nonce = input_field.get('value')
        if nonce:
            print(f"input 필드에서 nonce 찾음: {nonce}")
            return nonce
    
    print("nonce를 찾을 수 없음")
    return ""

def get_members_data(params, cookies):
    """AJAX 요청으로 회원 데이터 가져오기"""
    all_members = []
    page = 1
    max_pages = 10  # 기본값
    
    # 페이지 수 설정
    if 'pages' in params and params['pages']:
        try:
            max_pages = int(params['pages'])
        except:
            pass
    
    print(f"AJAX 요청으로 회원 데이터 수집 시작 (최대 {max_pages} 페이지)...")
    
    # 헤더 설정
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': f"{base_url}/members/",
        'Origin': base_url
    }
    
    # 쿠키 문자열 생성
    cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
    if cookie_str:
        headers['Cookie'] = cookie_str
    
    # 각 액션 시도
    actions = ['um_get_members', 'um_load_more_members']
    success = False
    
    for action in actions:
        if success:
            break
        
        print(f"\n'{action}' 액션 시도 중...")
        page = 1
        
        while page <= max_pages:
            print(f"페이지 {page}/{max_pages} 요청 중...")
            
            # 요청 데이터 구성
            data = {
                'action': action,
                'page': str(page),
                'directory_id': params.get('directory_id', 'default'),
                'hash': params.get('hash', ''),
                'nonce': params.get('nonce', '')
            }
            
            # um_get_members에 필요한 추가 파라미터
            if action == 'um_get_members':
                data['members_page'] = '1'
            
            try:
                # 요청 전 정보 표시
                print(f"요청 URL: {ajax_url}")
                print(f"요청 헤더: {headers}")
                print(f"요청 데이터: {data}")
                
                # AJAX 요청 보내기
                response = requests.post(ajax_url, headers=headers, data=data)
                
                # 응답 확인
                print(f"응답 상태 코드: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        # JSON 파싱 시도
                        json_data = response.json()
                        print(f"응답 JSON: {json.dumps(json_data)[:200]}..." if len(json.dumps(json_data)) > 200 else json.dumps(json_data))
                        
                        # 성공 확인
                        if json_data.get('success') == True:
                            success = True
                            
                            # 회원 데이터 추출
                            if 'users' in json_data:
                                members = json_data['users']
                            elif 'data' in json_data and 'users' in json_data['data']:
                                members = json_data['data']['users']
                            else:
                                print(f"응답에서 회원 데이터를 찾을 수 없습니다.")
                                if 'html' in json_data:
                                    print("HTML 응답에서 회원 데이터 추출 시도...")
                                    members = extract_member_data_from_html(json_data['html'])
                                else:
                                    members = []
                            
                            if not members:
                                print(f"페이지 {page}에 회원 데이터가 없습니다.")
                                break
                            
                            # 회원 데이터 추가
                            all_members.extend(members)
                            print(f"페이지 {page}에서 {len(members)}명의 회원 데이터를 가져왔습니다.")
                            
                            # 마지막 페이지 확인
                            if 'pagination' in json_data and 'pages' in json_data['pagination']:
                                max_pages = int(json_data['pagination']['pages'])
                                print(f"페이지네이션 정보: 총 {max_pages} 페이지")
                            
                            if page >= max_pages:
                                print("마지막 페이지에 도달했습니다.")
                                break
                        else:
                            error_msg = json_data.get('data', '알 수 없는 오류')
                            print(f"요청 실패: {error_msg}")
                            
                            if "잘못된 Nonce" in str(error_msg):
                                print("nonce가 유효하지 않습니다.")
                                break
                            
                    except json.JSONDecodeError:
                        print("응답이 JSON 형식이 아닙니다.")
                        print(f"응답 텍스트: {response.text[:200]}..." if len(response.text) > 200 else response.text)
                        
                        # HTML 응답일 수 있으므로 파싱 시도
                        if '<div class="um-member"' in response.text:
                            print("HTML 응답에서 회원 데이터 추출 시도...")
                            members = extract_member_data_from_html(response.text)
                            if members:
                                success = True
                                all_members.extend(members)
                                print(f"HTML에서 {len(members)}명의 회원 데이터를 추출했습니다.")
                        
                        if not success:
                            break
                else:
                    print(f"요청 실패: 상태 코드 {response.status_code}")
                    print(f"응답 텍스트: {response.text[:200]}..." if len(response.text) > 200 else response.text)
                    break
                    
                # 다음 페이지로
                page += 1
                
                # 요청 사이에 지연 추가
                time.sleep(2)
                
            except Exception as e:
                print(f"요청 중 오류 발생: {str(e)}")
                break
    
    return all_members

def extract_member_data_from_html(html_content):
    """HTML에서 회원 데이터 추출 (개선된 버전)"""
    members = []
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 모든 회원 요소 찾기 (다양한 선택자 시도)
    member_elements = soup.select('.um-member')
    
    if not member_elements:
        print("기본 선택자로 회원을 찾을 수 없습니다. 대체 선택자 시도...")
        member_elements = soup.select('[class*="um-member"]')
    
    print(f"HTML에서 {len(member_elements)}개의 회원 요소를 찾았습니다.")
    
    for elem in member_elements:
        try:
            member = {}
            
            # ID 추출 - 다양한 방법 시도
            member_id = elem.get('data-member-id', '')
            if not member_id:
                # ID가 없으면 프로필 URL에서 추출 시도
                profile_link = elem.select_one('a[href*="/user/"]')
                if profile_link:
                    url = profile_link.get('href', '')
                    # URL에서 사용자 이름 추출 (예: /user/username/)
                    match = re.search(r'/user/([^/]+)', url)
                    if match:
                        member_id = match.group(1)
            
            member['id'] = member_id or f"unknown-{len(members)}"
            
            # 이름 추출 - 다양한 선택자 시도
            name_selectors = ['.um-member-name', '.um-member-name a', '[class*="name"]', 'h3', '.um-member-card-header']
            for selector in name_selectors:
                name_elem = elem.select_one(selector)
                if name_elem:
                    member['name'] = name_elem.get_text(strip=True)
                    break
            
            # 프로필 URL 추출
            profile_link = elem.select_one('a[href*="/user/"]') or elem.select_one('a')
            if profile_link:
                member['profile_url'] = profile_link.get('href', '')
            
            # 메타데이터 추출 - 다양한 선택자 시도
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
                        # 메타 이름/값 쌍 찾기
                        meta_name_elem = meta.select_one('.um-meta-name') or meta.select_one('strong') or meta.select_one('label')
                        meta_value_elem = meta.select_one('.um-meta-value') or meta.select_one('span:not(.um-meta-name)') or meta.select_one('p')
                        
                        if meta_name_elem and meta_value_elem:
                            field_name = meta_name_elem.get_text(strip=True).lower().replace(' ', '_')
                            member[field_name] = meta_value_elem.get_text(strip=True)
                        elif not meta_name_elem and meta_value_elem:
                            # 이름이 없는 경우, 부모 요소의 클래스를 필드 이름으로 사용
                            class_name = meta.get('class', ['unknown'])
                            field_name = class_name[0].lower().replace('um-', '').replace('-', '_') if class_name else 'info'
                            member[field_name] = meta_value_elem.get_text(strip=True)
                        elif meta.get_text(strip=True):
                            # 단일 텍스트 블록인 경우
                            text = meta.get_text(strip=True)
                            if ':' in text:
                                parts = text.split(':', 1)
                                field_name = parts[0].strip().lower().replace(' ', '_')
                                member[field_name] = parts[1].strip()
                            else:
                                member[f'info_{len(member)}'] = text
            
            # 추가 정보: 역할이나 배지 추출
            role_elem = elem.select_one('.um-member-role') or elem.select_one('[class*="role"]')
            if role_elem:
                member['role'] = role_elem.get_text(strip=True)
            
            # 추가 정보: 온라인 상태
            if elem.select_one('.um-online-status.online'):
                member['online_status'] = 'online'
                
            # 이미지 URL 추출
            img_elem = elem.select_one('img.um-avatar') or elem.select_one('img')
            if img_elem:
                member['avatar_url'] = img_elem.get('src', '')
                
            members.append(member)
            
        except Exception as e:
            print(f"회원 요소 처리 중 오류: {str(e)}")
            continue
    
    return members

def save_data(members):
    """수집된 데이터 저장"""
    if not members:
        print("저장할 회원 데이터가 없습니다.")
        return
        
    # 원본 데이터 저장
    with open("members_data.json", "w", encoding="utf-8") as f:
        json.dump(members, f, indent=2, ensure_ascii=False)
        
    print(f"총 {len(members)}명의 회원 데이터가 'members_data.json'에 저장되었습니다.")
    
    # SWV Schema 형식으로 변환
    schema = {
        "version": "Contact Form 7 SWV Schema 2024-10",
        "locale": "ko_KR",
        "rules": []
    }
    
    for member in members:
        member_id = member.get("id", "unknown")
        
        # 각 필드에 대한 규칙 생성
        for field_name, value in member.items():
            if field_name in ["id", "profile_url"]:
                continue  # ID와 프로필 URL은 건너뜀
            
            form_field_name = f"member-{member_id}-{field_name}"
            
            # 필수 필드 규칙
            schema["rules"].append({
                "rule": "required",
                "field": form_field_name,
                "error": f"{field_name.replace('_', ' ')} 필드를 채워주세요."
            })
            
            # 최대 길이 규칙
            schema["rules"].append({
                "rule": "maxlength",
                "field": form_field_name,
                "threshold": 400,
                "error": f"{field_name.replace('_', ' ')} 필드가 너무 깁니다."
            })
            
            # 이메일 필드 검증
            if "email" in field_name:
                schema["rules"].append({
                    "rule": "email",
                    "field": form_field_name,
                    "error": "유효한 이메일 주소를 입력하세요."
                })
    
    # 스키마 저장
    with open("members_schema.json", "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
        
    print(f"Contact Form 7 SWV Schema가 'members_schema.json'에 저장되었습니다.")



def main():
    driver = None
    try:
        print("Selenium WebDriver 초기화 중...")
        driver = setup_driver()
        
        # 회원 페이지 분석 및 파라미터 추출
        params, cookies = analyze_members_page(driver)
        
        # 중요: 올바른 directory_id 설정
        # 로그에서 디렉토리 요소의 data-hash 값이 있으면 그것을 directory_id로 사용
        if 'hash' in params and params['hash']:
            params['directory_id'] = params['hash']
            print(f"directory_id를 hash 값으로 설정: {params['directory_id']}")
        
        # HTML에서 직접 회원 데이터 추출 (AJAX가 실패하더라도 초기 데이터는 수집)
        print("페이지에서 직접 회원 데이터 추출 중...")
        initial_members = extract_member_data_from_html(driver.page_source)
        print(f"HTML에서 {len(initial_members)}명의 회원 데이터를 추출했습니다.")
        
        # 브라우저 닫기 (더 이상 필요 없음)
        driver.quit()
        driver = None
        
        # AJAX 요청으로 회원 데이터 가져오기 시도
        ajax_members = get_members_data(params, cookies)
        
        # 두 소스의 데이터 병합 (중복 제거)
        all_members = initial_members.copy()
        
        # ajax_members에서 가져온 데이터가 있으면 추가 (중복 아이디 확인)
        if ajax_members:
            existing_ids = {member['id'] for member in all_members if 'id' in member}
            for member in ajax_members:
                if 'id' in member and member['id'] not in existing_ids:
                    all_members.append(member)
                    existing_ids.add(member['id'])
        
        print(f"총 {len(all_members)}명의 회원 데이터를 수집했습니다.")
        
        # 데이터 저장
        save_data(all_members)
        
    except Exception as e:
        print(f"프로그램 실행 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            driver.quit()
            print("WebDriver 종료됨")

if __name__ == "__main__":
    main()