import os
import re

frontend_dir = r"c:\CRM\frontend"
version_tag = "8.0"

html_files = [f for f in os.listdir(frontend_dir) if f.endswith(".html")]

updated_count = 0
for fname in html_files:
    fpath = os.path.join(frontend_dir, fname)
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()

    # Update css links: href="css/xxx.css..." -> href="css/xxx.css?v=6.0"
    new_content = re.sub(r'href="(css/[a-zA-Z0-9_\-]+\.css)(\?v=[^"]*)?"', f'href="\\1?v={version_tag}"', content)
    
    # Update js scripts: src="js/xxx.js..." -> src="js/xxx.js?v=6.0"
    new_content = re.sub(r'src="(js/[a-zA-Z0-9_\-]+\.css|\.js)(\?v=[^"]*)?"', f'src="\\1?v={version_tag}"', new_content)
    new_content = re.sub(r'src="(js/[a-zA-Z0-9_\-]+\.js)(\?v=[^"]*)?"', f'src="\\1?v={version_tag}"', new_content)

    if new_content != content:
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(new_content)
        updated_count += 1
        print(f"Updated cache-busting in: {fname}")

print(f"Total HTML files updated with cache busting: {updated_count}/{len(html_files)}")
