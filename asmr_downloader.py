from __future__ import annotations
import asyncio
import aiohttp
import os
import sys
from pathlib import Path
import json

class ASMR_DL():
    BASE_ENDPOINT = "https://as.mr"
    def __init__(self : ASMR_DL) -> None:
        self.http : aiohttp.ClientSession = None
        self.ENDPOINTS : dict[str, str] = None
        self.cur_endp : int = 0

    async def init_endpoint(self : ASMR_DL) -> None:
        html : list[str] = (await self.get_str(self.BASE_ENDPOINT)).split("<script ")
        for i in range(1, len(html)):
            script : str = html[i].split('src="', 1)[1].split('"')[0]
            parts : list[str] = (await self.get_str(self.BASE_ENDPOINT + script)).split("[{")
            for j in range(1, len(parts)):
                if "https://asmr" in parts[j]:
                    json_data : str = json.loads(("[{" + parts[j].split("}]", 1)[0] + "}]").replace('{', '{"').replace(':"', '":"').replace('",', '","'))
                    self.ENDPOINTS = {d["title"]:d["link"].replace("https://", "https://api.") for d in json_data}
                    break
            if self.ENDPOINTS is not None:
                break

    async def get_str(self : ASMR_DL, url : str) -> str:
        async with self.http.get(url) as response:
            if response.status == 200:
                return (await response.read()).decode('utf-8')
            else:
                raise Exception("HTTP Error {}".format(response.status))

    async def get_json(self : ASMR_DL, url : str) -> str:
        async with self.http.get(url) as response:
            if response.status == 200:
                return await response.json()
            else:
                raise Exception("HTTP Error {}".format(response.status))

    async def download_file(self : ASMR_DL, src_url : str, dst_file : Path) -> None:
        async with self.http.get(src_url) as response:
            if response.status == 200:
                with open(dst_file.as_posix(), mode="wb") as f:
                    async for data in response.content.iter_chunked(10485760):
                        f.write(data)
            else:
                raise Exception("HTTP Error {}".format(response.status))

    def get_endpoint(self : ASMR_DL) -> str:
        return list(self.ENDPOINTS.values())[self.cur_endp]

    def convert_track(self : ASMR_DL, track : dict|list, path : str = "") -> None:
        output : list[dict] = []
        if isinstance(track, list):
            for t in track:
                output.extend(self.convert_track(t, path))
        elif track["type"] == "folder":
            for t in track["children"]:
                output.extend(self.convert_track(t, path + "/" + track["title"]))
        else:
            output.append({"type":track["type"], "url":track["mediaDownloadUrl"], "title":path + "/" + track["title"], "size":track["size"], "download":True})
        return output

    def format_size(self : ASMR_DL, value : int) -> str:
        if value >= 1073741824:
            return "{:.1f}GB".format(value / 1073741824.0)
        elif value >= 1048576:
            return "{:.1f}MB".format(value / 1048576.0)
        elif value >= 1024:
            return "{:.1f}KB".format(value / 1024.0)
        else:
            return "{}B".format(value)

    async def download_task(self : ASMR_DL, queue : asyncio.Queue, counter : list[int]) -> None:
        while True:
            try:
                file_path, f, mode = queue.get_nowait()
            except:
                return
            try:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                await self.download_file(f["url"], file_path)
            except Exception as e:
                print("\nAn error occured, a file has been skipped:\n", e)
                continue
            counter[0] += 1
            sys.stdout.write("\rProgress {} / {}  ".format(counter[0], counter[1]))
            sys.stdout.flush()

    async def download(self : ASMR_DL, code : str, files : list[dict]) -> bool:
        base_path : Path = Path(code)
        mode : int = 0
        if os.path.isdir(base_path):
            print("")
            print("Folder", code, "already exist, what do you want to do?")
            print("[0] Overwrite everything")
            print("[1] Only redownload what's needed")
            print("[2] Cancel")
            while True:
                s = input()
                if s == "0":
                    mode = 0
                    break
                elif s == "1":
                    mode = 1
                    break
                elif s == "0":
                    return False
                else:
                    print("Invalid choice.")
        else:
            base_path.mkdir(parents=True, exist_ok=True)
        filecount : int = 0
        queue : asyncio.Queue = asyncio.Queue()
        for f in files:
            if f["download"]:
                file_path : Path = (base_path / f["title"][1:]) if f["title"].startswith('/') else (base_path / f["title"])
                if mode == 1 and os.path.isfile(file_path):
                    continue
                queue.put_nowait((file_path, f, mode))
                filecount += 1
        if filecount == 0:
            print("You must select at least one file to download.")
            return False
        print(filecount, "file(s) will be downloaded.")
        if input("Type 'start' to confirm the download:").lower() != "start":
            return False
        print("Downloading", filecount, "file(s)...")
        if mode == 1:
            print("(Files already present on disk will be ignored)")
        sys.stdout.write("Progress 0 / {}".format(filecount))
        sys.stdout.flush()
        counter : list[int] = [0, filecount]
        await asyncio.gather(
            self.download_task(queue, counter),
            self.download_task(queue, counter),
            self.download_task(queue, counter),
            self.download_task(queue, counter),
            self.download_task(queue, counter)
        )
        print("")
        return True

    async def open_management(self : ASMR_DL, code : str, data : dict) -> None:
        tracks : dict = await self.get_json(self.get_endpoint() + "api/tracks/" + code + "?v=1")
        content : list[dict] = self.convert_track(tracks)
        print("Title:", data["title"])
        print("Work ID:", data["id"])
        print(len(data["tags"]), "tag(s)")
        offset = 0
        while True:
            print("")
            print(" # DL  Size     Path")
            for i in range(offset, min(offset+10, len(content))):
                print("[{}][{}] {} {}".format(i-offset, "O" if content[i]["download"] else " ", self.format_size(content[i]["size"]), content[i]["title"]))
            print("[Number] to toggle the Download Status of the file.")
            if len(content) > 10:
                print("[P] Previous Page [N] Next Page")
            print("[D] Download [B] Back")
            s = input(":").lower()
            if s != "" and s in "0123456789":
                index = offset + int(s)
                if 0 <= index < len(content):
                    content[index]["download"] = not content[index]["download"]
            elif s == "n":
                offset += 10
                if offset >= len(content):
                    offset = 0
            elif s == "p":
                offset -= 10
                if offset < 0:
                    offset = (len(content) // 10) * 10
            elif s == "b":
                break
            elif s == "d":
                if await self.download(code, content):
                    break

    def get_code_from_name(self : ASMR_DL, name : str) -> str|None:
        names : list[str] = name.lower().split(".", 1)[0].split(" ")
        for n in names:
            if (n.startswith("re") or n.startswith("rj")) and len(n) >= 8 and n[2:].isdigit():
                return n[2:]
            elif len(n) >= 8 and n.isdigit():
                return n
        return None

    def iterdir(self : ASMR_DL, directory : Path) -> dict:
        table = {}
        for p in directory.iterdir():
            if p.is_file():
                if p.suffix in (".zip", ".rar", ".7z", ".tar", ".gz", ".gar"):
                    code : str|None = self.get_code_from_name(p.name)
                    if code is not None:
                        table[code] = {"path":p.as_posix()}
            elif p.is_dir():
                code : str|None = self.get_code_from_name(p.name)
                if code is None:
                    table = table | self.iterdir(p)
                else:
                    table[code] = {"path":p.as_posix()}
        return table

    def generate_indexhtml(self : ASMR_DL, path : Path, table : dict) -> None:
        html : list[str] = ["""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Sortable and Searchable Table</title>
  <style>
    body {
      font-family: Arial, sans-serif;
    }
    #searchContainer {
      text-align: center;
      margin: 20px;
    }
    #searchBar {
      width: 80%;
      padding: 8px;
      font-size: 16px;
    }
    table {
      border-collapse: collapse;
      width: 80%;
      margin: 20px auto;
    }
    th, td {
      padding: 8px 16px;
      border: 1px solid #ccc;
    }
    th {
      cursor: pointer;
      background-color: #f4f4f4;
    }
  </style>
</head>
<body>
  <div id="searchContainer">
    <input id="searchBar" type="text" placeholder="Search..." />
  </div>
  <table id="dataTable">
    <thead>
      <tr>
        <!-- data-type attribute to indicate sorting type -->
        <th data-type="number">ID</th>
        <th data-type="number">Path</th>
        <th data-type="string">Title</th>
        <th data-type="string">Circle</th>
        <th data-type="string">Tags</th>
      </tr>
    </thead>
    <tbody>
"""]

        for wid, data in table.items():
            html.append("""      <tr>
        <td>{}</td>
        <td>{}</td>
        <td>{}</td>
        <td>{}</td>
        <td>{}</td>
      </tr>
""".format(wid, data["path"], data.get("title", "NO TITLE"), data.get("name", ""), ", ".join(data.get("tags", []))))

        html.append("""    </tbody>
  </table>

  <script>
    document.addEventListener('DOMContentLoaded', () => {
      const table = document.getElementById('dataTable');
      const headers = table.querySelectorAll('th');
      const searchBar = document.getElementById('searchBar');
      // Maintain sort order for each column: default is ascending
      let sortOrders = Array(headers.length).fill('asc');

      // Function to perform sorting by column index and type (number/string)
      const sortColumn = (index, type) => {
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));

        rows.sort((rowA, rowB) => {
          let cellA = rowA.children[index].textContent.trim();
          let cellB = rowB.children[index].textContent.trim();

          if (type === 'number') {
            cellA = parseFloat(cellA);
            cellB = parseFloat(cellB);
          }

          if (cellA < cellB) return sortOrders[index] === 'asc' ? -1 : 1;
          if (cellA > cellB) return sortOrders[index] === 'asc' ? 1 : -1;
          return 0;
        });

        // Toggle sort order for subsequent clicks
        sortOrders[index] = sortOrders[index] === 'asc' ? 'desc' : 'asc';

        // Reinsert sorted rows into the tbody
        while (tbody.firstChild) {
          tbody.removeChild(tbody.firstChild);
        }
        rows.forEach(row => tbody.appendChild(row));
      };

      // Attach click listeners to each header for sorting
      headers.forEach((header, index) => {
        header.addEventListener('click', () => {
          const type = header.getAttribute('data-type');
          sortColumn(index, type);
        });
      });

      // Search functionality: filter rows based on search input
      searchBar.addEventListener('input', () => {
        const filter = searchBar.value.trim().toLowerCase();
        const tbody = table.querySelector('tbody');
        const rows = tbody.querySelectorAll('tr');

        rows.forEach(row => {
          // Check if any cell in the row contains the filter string
          const cells = Array.from(row.children);
          const isMatch = cells.some(cell => cell.textContent.toLowerCase().includes(filter));
          row.style.display = filter === '' || isMatch ? '' : 'none';
        });
      });
    });
  </script>
</body>
</html>""")
        with open(path / "index.html", mode="w", encoding="utf-8") as f:
            f.write("".join(html))
        print(path / "index.html", "has been generated")

    async def run(self : ASMR_DL) -> None:
        async with aiohttp.ClientSession() as self.http:
            await self.init_endpoint()
            if len(self.ENDPOINTS) == 0:
                raise Exception("No endpoints")
            else:
                print(len(self.ENDPOINTS), "endpoint(s) loaded")
                for e, u in self.ENDPOINTS.items():
                    print(e, "-", u)
            print("ASMR Downloader v1.1")
            while True:
                print("")
                print("[0] Download a work")
                print("[1] Generate index.html")
                print("[2] Change endpoint (Current: " + self.get_endpoint() + ")")
                print("[3] Quit")
                match input():
                    case "0":
                        code : str = input("Input a work code (Blank to cancel):").strip()
                        if code == "":
                            continue
                        elif code.startswith("RJ"):
                            code = code[2:]
                        try:
                            data : dict = await self.get_json(self.get_endpoint() + "api/workInfo/" + code)
                            await self.open_management(code, data)
                        except:
                            print("Work", code, "possibly not found")
                    case "1":
                        try:
                            base_path : Path = Path(input("Input the root folder path (Leave blank to use the current directory):"))
                        except Exception as e:
                            print("Exception:", e)
                            print("Aborted...")
                            continue
                        table : dict = self.iterdir(base_path)
                        for k in table:
                            try:
                                infos : dict = await self.get_json(self.get_endpoint() + "api/workInfo/" + k + "?v=1")
                            except:
                                print(k, "not found")
                                continue
                            table[k]["title"] = infos["title"]
                            table[k]["name"] = infos["name"]
                            table[k]["tags"] = []
                            for t in infos["tags"]:
                                if "i18n" in t and "en-us" in t["i18n"] and t["i18n"]["en-us"].get("name", None) is not None:
                                    table[k]["tags"].append(t["i18n"]["en-us"]["name"])
                                elif t.get("name", None) is not None:
                                    table[k]["tags"].append(t["name"])
                            print("Added", k)
                        self.generate_indexhtml(base_path, table)
                    case "2":
                        self.cur_endp = (self.cur_endp + 1) % len(self.ENDPOINTS)
                    case "3":
                        break
                    case _:
                        pass

if __name__ == "__main__":
    asyncio.run(ASMR_DL().run())