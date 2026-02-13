import os
import json
import gzip

data_dir = "data/paloma/c4_100_domains/val"
domain_list = []

for filename in os.listdir(data_dir):
    file_path = os.path.join(data_dir, filename)
    if os.path.isfile(file_path):
        try:
            with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        if 'subdomain' in data:
                            print(data['subdomain'])
                            subdomain = data['subdomain'].split("_")[1]
                            domain_list.append(subdomain)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            continue


unique_domains = list(set(domain_list))
with open('data/paloma/c4_100_domains/domain_list.txt', 'w', encoding='utf-8') as f:
    for domain in unique_domains:
        f.write(domain + '\n')
