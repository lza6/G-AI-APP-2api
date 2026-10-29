# -*- coding: utf-8 -*-
"""demo 页真实浏览器验证（Playwright）"""
import sys

sys.stdout.reconfigure(encoding="utf-8")

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8970/"

with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1280, "height": 800})
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(URL, wait_until="networkidle")
    page.wait_for_selector(".dot.on", timeout=20000)
    opts = page.eval_on_selector_all("#model option", "els => els.map(e => e.value)")
    print("网关就绪标记: OK")
    print("模型下拉数量:", len(opts), opts[:3])
    page.fill("#input", "hello, reply with OK")
    page.click("#send")
    page.wait_for_function(
        "() => document.querySelectorAll('.msg.bot').length > 0 && "
        "document.querySelector('.msg.bot').textContent.trim().length > 0",
        timeout=90000)
    bot = page.inner_text(".msg.bot")
    print("机器人回复:", bot[:160].replace("\n", " "))
    print("首字延迟:", page.inner_text("#ttfb"), "总耗时:", page.inner_text("#total"))
    print("事件数:", page.inner_text("#evn"))
    page.screenshot(path="demo_proof.png", full_page=False)
    print("截图: demo_proof.png")
    if errors:
        print("console errors:", errors[:5])
    b.close()
