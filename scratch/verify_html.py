from html.parser import HTMLParser
import sys

class Verifier(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.errors = []
        
    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, self.getpos()))
        
    def handle_endtag(self, tag):
        if not self.tags:
            self.errors.append(f"Unexpected end tag </{tag}> at line {self.getpos()[0]}")
            return
        last_tag, pos = self.tags.pop()
        if last_tag != tag:
            # Check if it's a self-closing tag that HTMLParser didn't realize
            if last_tag in ['meta', 'link', 'img', 'br', 'hr', 'input']:
                # Pop again
                if self.tags:
                    last_tag, pos = self.tags.pop()
            if last_tag != tag:
                self.errors.append(f"Mismatched tag: started <{last_tag}> at line {pos[0]}, but closed </{tag}> at line {self.getpos()[0]}")

def main():
    filename = "scratch_report.html"
    try:
        with open(filename, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {filename}: {e}")
        return
        
    parser = Verifier()
    try:
        parser.feed(content)
        print("Parsing completed.")
        if parser.errors:
            print(f"Found {len(parser.errors)} errors:")
            for err in parser.errors[:10]:
                print(f" - {err}")
        else:
            print("No structural HTML mismatch errors found.")
    except Exception as e:
        print(f"Parser crashed: {e}")

if __name__ == "__main__":
    main()
