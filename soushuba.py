# -*- coding: utf-8 -*-
"""
实现搜书吧论坛登入和发布空间动态
"""
import os
import re
import sys
from copy import copy
import random

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
from bs4 import BeautifulSoup
from lxml import etree
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import time
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

ch = logging.StreamHandler(stream=sys.stdout)
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger.addHandler(ch)

def get_refresh_url(url: str):
    try:
        response = requests.get(url, verify=False)
        if response.status_code != 403:
            response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        meta_tags = soup.find_all('meta', {'http-equiv': 'refresh'})

        if meta_tags:
            content = meta_tags[0].get('content', '')
            if 'url=' in content:
                redirect_url = content.split('url=')[1].strip()
                print(f"Redirecting to: {redirect_url}")
                return redirect_url
        else:
            print("No meta refresh tag found.")
            return None
    except Exception as e:
        print(f'An unexpected error occurred: {e}')
        return None

def get_url(url: str):
    resp = requests.get(url, verify=False)
    soup = BeautifulSoup(resp.content, 'html.parser')
    
    links = soup.find_all('a', href=True)
    for link in links:
        if link.text == "搜书吧":
            return link['href']
    return None

class SouShuBaClient:

    def __init__(self, hostname: str, username: str, password: str, questionid: str = '0', answer: str = None,
                 proxies: dict | None = None):
        self.session: requests.Session = requests.Session()
        self.session.verify = False  # 禁用SSL证书验证
        self.hostname = hostname
        self.username = username
        self.password = password
        self.questionid = questionid
        self.answer = answer
        self._common_headers = {
            "Host": f"{ hostname }",
            "Connection": "keep-alive",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,cn;q=0.9",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        self.proxies = proxies
        self.last_post_time = 0.0 # Track last successful post time across methods

    def _wait_for_rate_limit(self, required_delay_seconds=61.0):
        """Checks time since last post and waits if necessary."""
        now = time.time()
        time_since_last_post = now - self.last_post_time
        if time_since_last_post < required_delay_seconds:
            wait_needed = required_delay_seconds - time_since_last_post
            logger.info(f"{self.username[0]}******{self.username[-1]}: Global rate limit: waiting {wait_needed:.1f} seconds before next post.")
            time.sleep(wait_needed)

    def login_form_hash(self):
        try:
            rst = self.session.get(f'https://{self.hostname}/member.php?mod=logging&action=login', verify=False).text
            loginhash = re.search(r'<div id="main_messaqge_(.+?)">', rst).group(1)
            formhash = re.search(r'<input type="hidden" name="formhash" value="(.+?)" />', rst).group(1)
            return loginhash, formhash
        except Exception as e:
            logger.error(f"Request failed when getting login hash/formhash for {self.username}: {e}")
            logger.error(f"Failed to get login hash/formhash for {self.username}")
            raise ValueError("Login preparation failed.")

    def login(self):
        """Login with username and password"""
        loginhash, formhash = self.login_form_hash()
        login_url = f'https://{self.hostname}/member.php?mod=logging&action=login&loginsubmit=yes' \
                    f'&handlekey=register&loginhash={loginhash}&inajax=1'


        headers = copy(self._common_headers)
        headers["origin"] = f'https://{self.hostname}'
        headers["referer"] = f'https://{self.hostname}/'
        payload = {
            'formhash': formhash,
            'referer': f'https://{self.hostname}/',
            'username': self.username,
            'password': self.password,
            'questionid': self.questionid,
            'answer': self.answer
        }

        resp = self.session.post(login_url, proxies=self.proxies, data=payload, headers=headers, verify=False)
        if resp.status_code == 200:
            logger.info(f'Welcome {self.username}!')
        else:
            raise ValueError('Verify Failed! Check your username and password!')

    def credit(self):
        credit_url = f"https://{self.hostname}/home.php?mod=spacecp&ac=credit&showcredit=1&inajax=1&ajaxtarget=extcreditmenu_menu"
        credit_rst = self.session.get(credit_url, verify=False).text

        # 解析 XML，提取 CDATA
        root = ET.fromstring(str(credit_rst))
        cdata_content = root.text

        # 使用 BeautifulSoup 解析 CDATA 内容
        cdata_soup = BeautifulSoup(cdata_content, features="lxml")
        hcredit_2 = cdata_soup.find("span", id="hcredit_2").string

        return hcredit_2

    def space_form_hash(self):
        rst = self.session.get(f'https://{self.hostname}/home.php?mod=spacecp&ac=credit&showcredit=1', verify=False).text
        formhash = re.search(r'<input type="hidden" name="formhash" value="(.+?)" />', rst).group(1)
        return formhash

    def space(self):
        formhash = self.space_form_hash()
        space_url = f"https://{self.hostname}/home.php?mod=spacecp&ac=doing&handlekey=doing&inajax=1"

        headers = copy(self._common_headers)
        headers["origin"] = f'https://{self.hostname}'
        headers["referer"] = f'https://{self.hostname}/home.php'

        for x in range(5):
            payload = {
                "message": "开心赚银币 {0} 次".format(x + 1).encode("GBK"),
                "addsubmit": "true",
                "spacenote": "true",
                "referer": "home.php",
                "formhash": formhash
            }
            resp = self.session.post(space_url, proxies=self.proxies, data=payload, headers=headers, verify=False)
            if re.search("操作成功", resp.text):
                logger.info(f'{self.username} post {x + 1}nd successfully!')
                time.sleep(120)
            else:
                logger.warning(f'{self.username} post {x + 1}nd failed!')

    def get_tids(self):
        fids=[40,39,68]
        url=f'https://{self.hostname}/forum.php?mod=forumdisplay&fid={random.choice(fids)}&page=1'
        # print(url)
        headers = copy(self._common_headers)
        headers["origin"] = f'https://{self.hostname}'
        headers["referer"] = f'https://{self.hostname}/forum.php'

        page_text=self.session.get(url=url,headers=headers).text

        page_root=etree.HTML(page_text)
        page_need=page_root.xpath("//table[@id='threadlisttableid']")
        # Add check for empty page_need
        if not page_need:
             logger.warning(f"Could not find threadlisttableid on page {url}")
             return []
        pattern = re.compile('tid=(\d+)&amp')
        page_need_text=str(etree.tostring(page_need[0]))
        tid_list = pattern.findall(page_need_text)
        tid_list_set = list(dict.fromkeys(tid_list))[10::]
        return tid_list_set
                
    def comment(self, tid):

        formhash = self.space_form_hash()
        # Check if formhash was obtained
        if not formhash:
            logger.error(f"Cannot comment on TID {tid} for {self.username[0]}******{self.username[-1]} because formhash could not be retrieved.")
            return -1 # Indicate failure

        message=['别的不说，楼主就是给力啊','谢谢楼主分享，祝搜书吧越办越好！','看了LZ的帖子，我只想说一句很好很强大！','太感谢了太感谢了太感谢了']
        commen=random.choice(message)
        commen_gbk = commen.encode('gbk')
        comment_payload = {
                'formhash': formhash,
                'handlekey': 'register',
                'noticeauthor': '',
                'noticetrimstr': '',
                'noticeauthormsg': '',
                'usesig': '1',
                'subject': '',
                'message': commen_gbk
            }
       # tid=random.choice(url_list)
        
        comment_url=f'https://{self.hostname}/forum.php?mod=post&infloat=yes&action=reply&fid=100&extra=&tid={tid}&replysubmit=yes&inajax=1'
        
        headers = copy(self._common_headers)
        headers["origin"] = f'https://{self.hostname}'
        headers["referer"] = f'https://{self.hostname}/forum.php?mod=viewthread&tid={tid}&extra='
        
        # Wait before attempting the post
        self._wait_for_rate_limit()

        comment_result=self.session.post(url=comment_url,headers=headers,data=comment_payload)
        # print(pinglun.text)
        if '发布成功' in comment_result.text :
            #logger.info(f'评论成功，此次评论的帖子tid为 {tid} ,评论的内容为 {commen} ,等待60s后再次评论')
            logger.info(f'{self.username[0]}******{self.username[-1]}: 评论成功{commen}') # Removed wait info here
            self.last_post_time = time.time() # Update last post time on success
            return 0
        elif '回复限制' in comment_result.text:
            logger.warning('重复评论')
        elif '发布间隔' in comment_result.text:
            logger.warning('评论太快，等待60s')

        else:
            logger.error(f'{self.username[0]}******{self.username[-1]}:comments failed')
            #logger.error(f'response：{comment_result.text}')
            
        return -1
    def comments(self):
        successful_comments_count = 0
        max_attempts_per_comment = 3 # Maximum attempts for a single comment tid
        total_attempts = 0 # Prevent potential infinite loops overall
        max_total_attempts = 15 # e.g., 3 comments * 5 attempts each

        tids = [] # Initialize empty list

        while successful_comments_count < 3 and total_attempts < max_total_attempts:
            total_attempts += 1

            # Fetch new TIDs if the list is empty or exhausted
            if not tids:
                logger.info("Fetching new TIDs for commenting...")
                tids = self.get_tids()
                # Shuffle to avoid always picking the same if retrying
                random.shuffle(tids)
                if not tids:
                    logger.error("Failed to fetch any TIDs, cannot continue commenting.")
                    break # Exit the main while loop if no TIDs can be fetched
                logger.info(f"Fetched {len(tids)} TIDs.")

            if not tids: # Double check after fetching
                 logger.warning("No TIDs available to comment on.")
                 time.sleep(60) # Wait before trying to fetch again
                 continue # Skip to next iteration of while loop

            tid_to_try = tids.pop(0) # Get the next TID from the list
            tid_display = f"{tid_to_try[:2]}****{tid_to_try[-2:]}" if len(str(tid_to_try)) > 4 else str(tid_to_try)
            logger.info(f"Attempting comment {successful_comments_count + 1}/3 on TID: {tid_display}")

            attempt = 0
            comment_succeeded = False
            while attempt < max_attempts_per_comment and not comment_succeeded:
                attempt += 1
                result = self.comment(tid_to_try)
                if result == 0:
                    successful_comments_count += 1
                    comment_succeeded = True
                    logger.info(f"Successfully posted comment {successful_comments_count}/3.")
                    # Wait after successful comment before the next one
                    if successful_comments_count < 3:
                         time.sleep(61) # Wait 61s as requested by logs previously
                else:
                    logger.warning(f"Attempt {attempt}/{max_attempts_per_comment} failed for TID {tid_display}. Retrying if possible...")
                    # If it failed due to interval, wait longer before retry
                    # Note: self.comment already logs specific reasons
                    if attempt < max_attempts_per_comment:
                        # Check the failure reason from the last comment attempt if possible
                        # (requires comment method to provide more info or check resp text here)
                        # For now, assume most failures need the long wait
                        logger.info(f"Waiting 61 seconds before retrying comment on TID {tid_display}...")
                        time.sleep(61)
                    else:
                         logger.error(f"Failed to comment on TID {tid_display} after {max_attempts_per_comment} attempts.")

            if not comment_succeeded and tids:
                 # If failed on this TID, maybe try another one next time without long sleep yet
                 logger.info("Trying next TID.")
            elif not comment_succeeded and not tids:
                 # If failed and no more TIDs, wait before fetching new ones
                 logger.info("Failed comment and no more TIDs. Waiting before fetching new list.")
                 time.sleep(60)


        if successful_comments_count < 3:
             logger.error(f"Could only complete {successful_comments_count} out of 3 required comments after {total_attempts} total attempts.")
        else:
             logger.info("Successfully completed 3 comments.")


if __name__ == '__main__':
    try:
        redirect_url = get_refresh_url('http://' + os.environ.get('SOUSHUBA_HOSTNAME', 'www.soushu2025.com'))
        time.sleep(2)
        redirect_url2 = get_refresh_url(redirect_url)
        url = get_url(redirect_url2)
        logger.info(f'{url}')
        
        credentials = json.loads(os.environ.get('MULTI_CREDS', '{"libesse":"yF9pnSBLH3wpnLd"}'))

        for username, password in credentials.items():
            client = SouShuBaClient(urlparse(url).hostname,
                                    username,
                                    password)
            client.login()
            client.space()
            client.comments()
            credit = client.credit()
            logger.info(f'{client.username} have {credit} coins!')
    except Exception as e:
        logger.error(e)
        sys.exit(1)
