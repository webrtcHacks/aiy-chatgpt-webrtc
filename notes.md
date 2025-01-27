    chrome_args = [
        "chromium-browser",
        "--remote-debugging-port=9222",  # enable DevTools protocol
        "--disable-gpu",
        "--autoplay-policy=no-user-gesture-required",
        "--allow-insecure-localhost",
        "--use-fake-ui-for-media-stream",
        "--unsafely-treat-insecure-origin-as-secure=http://localhost:3000",
        # "--incognito",
        # "--disk-cache-dir=/dev/null",
        # "--disk-cache-size=1",
        # "--media-cache-size=1",
        # "--auto-open-devtools-for-tabs",
        "about:blank",  # load this initially
    ]