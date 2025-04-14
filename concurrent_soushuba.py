# -*- coding: utf-8 -*-
"""
并发执行搜书吧论坛登入、发布空间动态和评论
"""
import os
import json
import logging
import sys
import time
from urllib.parse import urlparse
import concurrent.futures

# 假设 SouShuBaClient, get_refresh_url, get_url 在 soushuba 模块中
# 如果它们在同一个文件中，需要相应调整导入
from soushuba import SouShuBaClient, get_refresh_url, get_url

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

ch = logging.StreamHandler(stream=sys.stdout)
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger.addHandler(ch)

def process_user(hostname, username, password):
    """
    Process login, and concurrently run space update and commenting for a single user.
    """
    try:
        client = SouShuBaClient(hostname, username, password)
        client.login()
        initial_credit = client.credit()
        logger.info(f'{client.username[0]}******{client.username[-1]} Initial coins: {initial_credit}')

        # Run space update and comments sequentially for this user
        logger.info(f"Running space task for {client.username[0]}******{client.username[-1]}")
        try:
            client.space()
        except Exception as e:
            logger.error(f"Error in space task for user {username}: {e}", exc_info=True)

        logger.info(f"Running comments task for {client.username[0]}******{client.username[-1]}")
        try:
            client.comments()
        except Exception as e:
            logger.error(f"Error in comments task for user {username}: {e}", exc_info=True)

        logger.info(f"Space and comments tasks completed sequentially for {client.username[0]}******{client.username[-1]}")

        # 在获取最终积分前增加延时
        logger.info(f"Waiting 1 seconds before fetching final credit for {client.username[0]}******{client.username[-1]}...")
        time.sleep(1)

        final_credit = client.credit()
        if final_credit is not None:
             logger.info(f'{client.username[0]}******{client.username[-1]} Final coins after concurrent operations: {final_credit}')
        else:
             logger.error(f"Failed to retrieve final credit for {client.username[0]}******{client.username[-1]}.")

    except Exception as e:
        logger.error(f'Error processing user {username}: {e}', exc_info=True)

if __name__ == '__main__':
    try:
        # Get target URL
        initial_host = os.environ.get('SOUSHUBA_HOSTNAME', 'www.soushu2025.com')
        redirect_url = get_refresh_url(f'http://{initial_host}')
        if not redirect_url:
            logger.error("Failed to get first redirect URL")
            sys.exit(1)
        time.sleep(2) # Allow for potential delays

        redirect_url2 = get_refresh_url(redirect_url)
        if not redirect_url2:
            logger.error("Failed to get second redirect URL")
            sys.exit(1)

        target_url = get_url(redirect_url2)
        if not target_url:
            logger.error("Failed to get final URL from redirect page")
            sys.exit(1)

        logger.info(f'Final target URL: {target_url}')
        hostname = urlparse(target_url).hostname
        if not hostname:
            logger.error(f"Failed to parse hostname from URL '{target_url}'")
            sys.exit(1)


        # Load credentials
       
        creds_json =os.environ.get('MULTI_CREDS') or '{"libesse":"yF9pnSBLH3wpnLd"}'
        if not creds_json:
            logger.error("Environment variable MULTI_CREDS is not set")
            sys.exit(1)

        try:
            credentials = json.loads(creds_json)
            if not isinstance(credentials, dict):
                raise ValueError("MULTI_CREDS must be a JSON dictionary")
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing MULTI_CREDS: {e}")
            sys.exit(1)
        except ValueError as e:
            logger.error(e)
            sys.exit(1)


        # Process users concurrently using a thread pool
        # Use ProcessPoolExecutor for CPU-bound tasks, ThreadPoolExecutor for I/O-bound tasks
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(credentials)) as executor:
            futures = []
            for username, password in credentials.items():
                futures.append(executor.submit(process_user, hostname, username, password))
                # 在提交每个用户任务之间增加短暂延时
                time.sleep(0.5)

            # Wait for all tasks to complete (optional, depends on whether results/exceptions need handling)
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result() # Get result or re-raise exception
                except Exception as e:
                    logger.error(f"A user processing task failed: {e}", exc_info=True)

        logger.info("All users processed.")

    except Exception as e:
        logger.error(f"Unhandled error during script execution: {e}", exc_info=True)
        sys.exit(1) 