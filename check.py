import requests
import concurrent.futures
import argparse
import os
import re
import sys
from datetime import datetime
import time
from collections import OrderedDict

try:
    from colorama import Fore, Style, init
    init()
except ImportError:
    class FakeColors:
        CYAN = GREEN = YELLOW = RED = WHITE = BLUE = RESET_ALL = ''
    Fore = FakeColors()
    Style = FakeColors()

# ======================
# 界面显示组件
# ======================
def print_banner():
    print(f"\n{Fore.CYAN}")
    print(r" ________________________________________________________________ ")
    print(r"|                                                                |")
    print(r"| ██████╗ ██████╗  ██████╗ ██╗  ██╗██╗   ██╗██████╗  ██████╗ ███████╗|")
    print(r"| ██╔══██╗██╔══██╗██╔═══██╗╚██╗██╔╝╚██╗ ██╔╝██╔══██╗██╔════╝ ██╔════╝|")
    print(r"| ██████╔╝██████╔╝██║   ██║ ╚███╔╝  ╚████╔╝ ██████╔╝██║  ███╗█████╗  |")
    print(r"| ██╔═══╝ ██╔══██╗██║   ██║ ██╔██╗   ╚██╔╝  ██╔══██╗██║   ██║██╔══╝  |")
    print(r"| ██║     ██║  ██║╚██████╔╝██╔╝ ██╗   ██║   ██████╔╝╚██████╔╝███████╗|")
    print(r"| ╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚═════╝  ╚═════╝ ╚══════╝|")
    print(r"|________________________________________________________v2.1.0___|")
    print(Style.RESET_ALL)

def print_status(args):
    print(f"{Fore.YELLOW}◈ 运行参数{Style.RESET_ALL}")
    print(f"{Fore.WHITE}├─ 代理文件: {Fore.GREEN}{args.file}{Style.RESET_ALL}")
    print(f"{Fore.WHITE}├─ 测试地址: {Fore.CYAN}{args.url}{Style.RESET_ALL}")
    print(f"{Fore.WHITE}├─ 超时时间: {Fore.RED}{args.timeout}s{Style.RESET_ALL}")
    print(f"{Fore.WHITE}└─ 并发线程: {Fore.BLUE}{args.threads}{Style.RESET_ALL}\n")

def print_progress(current, total, start_time):
    bar_length = 30
    elapsed = time.time() - start_time
    progress = current / total
    
    filled = int(bar_length * progress)
    bar = f"{Fore.GREEN}█" * filled + f"{Fore.WHITE}░" * (bar_length - filled)
    
    eta = (elapsed / current) * (total - current) if current else 0
    eta_str = f"{eta:.1f}s" if current else "N/A"
    
    sys.stdout.write(
        f"\r{Fore.CYAN}┫{bar}{Fore.CYAN}┣ "
        f"{current}/{total} ({progress:.0%}) "
        f"[ETA: {eta_str}]"
    )
    sys.stdout.flush()

def print_result(valid, total, time_cost, filename):
    print(f"\n{Fore.CYAN}◈ 检测统计{Style.RESET_ALL}")
    print(f"{Fore.WHITE}├─ 总检测量: {total}")
    print(f"{Fore.WHITE}├─ 可用代理: {Fore.GREEN}{valid}{Style.RESET_ALL}")
    print(f"{Fore.WHITE}├─ 不可用量: {Fore.RED}{total - valid}{Style.RESET_ALL}")
    print(f"{Fore.WHITE}├─ 总耗时: {Fore.YELLOW}{time_cost:.2f}s{Style.RESET_ALL}")
    print(f"{Fore.WHITE}└─ 结果文件: {Fore.CYAN}{filename}{Style.RESET_ALL}\n")

# ======================
# 核心功能
# ======================
def clean_proxy(line):
    line = re.sub(r"^\w+://", "", line)  # 移除协议头
    line = line.split("@")[-1]           # 移除认证信息
    
    if not re.match(r"^\d{1,3}(\.\d{1,3}){3}:\d+$", line):
        return None
    return line

def check_proxy(proxy_line, test_url, timeout):
    clean_line = clean_proxy(proxy_line)
    if not clean_line:
        return {"status": "invalid", "raw": proxy_line}

    proxies = {
        "http": f"http://{clean_line}",
        "https": f"http://{clean_line}"
    }

    try:
        start = time.time()
        res = requests.get(
            test_url,
            proxies=proxies,
            timeout=timeout,
            headers={"User-Agent": "ProxyChecker/2.1"}
        )
        if res.status_code == 200:
            return {
                "status": "valid",
                "clean": clean_line,
                "raw": proxy_line,
                "time": time.time() - start
            }
        return {"status": "invalid", "raw": proxy_line}
    except requests.exceptions.ProxyError:
        return {"status": "invalid", "raw": proxy_line, "error": "无法连接"}
    except requests.exceptions.ConnectTimeout:
        return {"status": "invalid", "raw": proxy_line, "error": "超时"}
    except Exception as e:
        return {"status": "invalid", "raw": proxy_line, "error": str(e)}

def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-f", "--file", required=True, help="代理列表文件路径")
    parser.add_argument("-u", "--url", required=True, help="测试URL地址")
    parser.add_argument("-t", "--timeout", type=float, default=3.0, help="超时时间（秒）")
    parser.add_argument("-p", "--threads", type=int, default=50, help="并发线程数")
    args = parser.parse_args()

    print_banner()
    print_status(args)

    if not os.path.exists(args.file):
        print(f"{Fore.RED}错误：文件 {args.file} 不存在{Style.RESET_ALL}")
        return

    with open(args.file) as f:
        origin_proxies = [line.strip() for line in f if line.strip()]
    
    total = len(origin_proxies)
    if total == 0:
        print(f"{Fore.RED}错误：文件为空{Style.RESET_ALL}")
        return

    valid_set = OrderedDict()
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.threads) as executor:
        futures = {executor.submit(check_proxy, line, args.url, args.timeout): line 
                 for line in origin_proxies}
        
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            completed += 1
            print_progress(completed, total, start_time)
            
            result = future.result()
            original = futures[future]
            
            if result["status"] == "valid":
                valid_set[result["clean"]] = None
                sys.stdout.write(f"\r{Fore.GREEN}✓ {original.ljust(25)} → {result['clean']}\n")
            else:
                error = result.get("error", "格式无效")
                sys.stdout.write(f"\r{Fore.RED}✗ {original.ljust(25)} → {error}\n")
            sys.stdout.flush()

    # 生成结果文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"proxies_{timestamp}.txt"
    
    with open(output_file, "w") as f:
        seen = set()
        for line in origin_proxies:
            clean = clean_proxy(line)
            if clean and clean in valid_set and clean not in seen:
                f.write(f"{clean}\n")
                seen.add(clean)

    # 清理进度条
    sys.stdout.write("\r" + " " * 80 + "\r")
    sys.stdout.flush()
    
    print_result(len(seen), total, time.time()-start_time, output_file)

if __name__ == "__main__":
    main()