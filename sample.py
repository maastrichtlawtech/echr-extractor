from echr_extractor import get_echr

# Example 1: Using query_payload (fixed format)
payload = "article:8"
df = get_echr(query_payload=payload, count=5, save_file="n")
print("Query payload result:", len(df), "records")

# Example 2: Using URL (fixed JSON structure)
url = "https://hudoc.echr.coe.int/eng#{%22itemid%22:[%22001-57574%22%5D}"
df2 = get_echr(link=url, save_file="n")
if df2 is not False:
    print("URL result:", len(df2), "records")
else:
    print("URL result: Failed to retrieve data")
