import pandas as pd
import numpy as np
import requests
import json
import re
import glob
import os
from datetime import datetime
import time
import copy
from tqdm import tqdm

from bs4 import BeautifulSoup as bs4

import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

print("Hello world... All import seem to be ok.")





# CONSTANTS --------------------------------------------------------------------------------------------------- # 

# set constants for data provider and data API
PROVIDER = "opendata.swiss"
PROVIDER_LINK = "https://opendata.swiss/"
BASELINK_DATAPORTAL = "https://opendata.swiss/de/dataset/"
CKAN_API_LINK = "https://opendata.swiss/api/3/action/current_package_list_with_resources"
LANGUAGE = "de"

# set constants in regard to GitHub account and repo
GITHUB_ACCOUNT = "rnckp"
REPO_NAME = "starter-code-opendataswiss"
REPO_BRANCH = "main"
REPO_RMARKDOWN_OUTPUT = "01_r-markdown/"
REPO_PYTHON_OUTPUT = "02_python/"
TEMP_PREFIX = "_work/"

# set local folders and file names
TEMPLATE_FOLDER = "_templates/"
TEMPLATE_README = "template_md_readme.md" # <- template for the README.md in the repo
TEMPLATE_HEADER = "template_md_header.md" # <- header for list overview that is rendered as a GitHub page
TEMPLATE_PYTHON = "template_python.ipynb"
TEMPLATE_RMARKDOWN = "template_rmarkdown.Rmd"
METADATA_FOLDER = "_metadata_json/"

TODAY_DATE = datetime.today().strftime('%Y-%m-%d')
TODAY_DATETIME = datetime.today().strftime("%Y-%m-%d %H:%M:%S")

# set max length of dataset title in markdown table
TITLE_MAX_CHARS = 200

# sort markdown table by this feature
SORT_TABLE_BY = f"title.{LANGUAGE}"

# select keys in metadata for dataset and distributions
KEYS_DATASET = ['publisher', f'organization.display_name.{LANGUAGE}', 
                "organization.url", "maintainer", "maintainer_email",
                f'keywords.{LANGUAGE}', 'issued', 'metadata_created', 
                'metadata_modified']
KEYS_DISTRIBUTIONS = ['package_id', "description", 'issued', 
                      'modified', "rights"]

# select relevant column names to reduce dataset 
REDUCED_FEATURESET = ['maintainer', 'issued', 'title_for_slug', 
                      'maintainer_email', 'contact_points', 'id',
                      'metadata_created', 'metadata_modified', 
                      'resources', 'groups', 'publisher', 'name',
                      'language', 'modified', 'url', 'identifier', 
                      'keywords.fr', 'keywords.de', 'keywords.en', 'keywords.it', 
                      'display_name.fr', 'display_name.de', 'display_name.en', 'display_name.it', 
                      'description.fr', 'description.de', 'description.en', 'description.it',
                      'organization.display_name.fr', 'organization.display_name.de',
                      'organization.display_name.en', 'organization.display_name.it',
                      'organization.name',  
                      'organization.title.fr', 'organization.title.de',
                      'organization.title.en', 'organization.title.it',
                      'title.fr', 'title.de', 'title.en', 'title.it', 
                      'metadata', 'contact', 'distributions', 'distribution_links']


# FUNCTIONS --------------------------------------------------------------------------------------------------- # 


def get_full_package_list(limit=500, sleep=2):
    """Get full package list from CKAN API"""
    offset = 0
    frames = []
    while True:
        print(f"{offset} packages retrieved.")
        url = CKAN_API_LINK + f"?limit={limit}&offset={offset}"
        res = requests.get(url)
        data = json.loads(res.content)
        if data["result"] == []:
            break
        data = pd.DataFrame(pd.json_normalize(data["result"]))
        frames.append(data)
        offset += limit
        time.sleep(sleep)
    data = pd.concat(frames)
    data.reset_index(drop=True, inplace=True)
    return data


def has_csv_distribution(dists):
    """Iterate over package resources and keep only CSV entries in list"""
    csv_dists = [x for x in dists if x.get("format", "") == "CSV"]
    if csv_dists != []:
        return csv_dists
    else:
        return np.nan
    
    
def filter_csv(data):
    """Remove all datasets that have no CSV distribution"""
    data.resources = data.resources.apply(has_csv_distribution)
    data.dropna(subset=["resources"], inplace=True)
    return data.reset_index(drop=True)


def clean_features(data):
    """Clean various features"""
    # reduce publisher data to name
    data.publisher = data.publisher.apply(lambda x: json.loads(x)["name"])
    
    # reduce tags to tag names
    data.tags = data.tags.apply(lambda x: [tag["name"] for tag in x])
    
    # replace empty urls with NA message
    data[data["organization.url"] == ""]["organization.url"] = "None provided"
    
    # if title in target language does not exist try to fill in english title
    idx = data[data[f"title.{LANGUAGE}"]==""].index
    data.loc[idx, f"title.{LANGUAGE}"] = data[f"title.en"]
    
    # remove HTML tags from description
    data[f"description.{LANGUAGE}"] = data[f"description.{LANGUAGE}"].apply(lambda x: bs4(x, "html.parser").text)
    
    # strip whitespace from title
    data[f"title.{LANGUAGE}"] = data[f"title.{LANGUAGE}"].map(lambda x: x.strip())
    
    return data


def prepare_data_for_codebooks(data):
    """Prepare metadata from catalogue in order to create the code files"""
    # add new features to save prepared data
    data["metadata"] = None
    data["contact"] = None
    data["distributions"] = None
    data["distribution_links"] = None
    
    # iterate over datasets and create additional data for markdown and code cells
    for idx in tqdm(data.index):
        md = [f"- **{k.capitalize()}** `{data.loc[idx, k]}`\n" for k in KEYS_DATASET]
        data.loc[idx, "metadata"] = "".join(md)
        
        contact_points = [x for x in data.loc[idx, "contact_points"][0].values() if x != {}]
        data.loc[idx, "contact"] = " | ".join(contact_points)

        tmp_dists = []
        tmp_links = []
        for dist in data.loc[idx, "resources"]:
            # some descriptions are strings rather than dicts with language keys
            if isinstance(dist["description"], dict):
                # filter description in specific language set by LANGUAGE
                if dist["description"][LANGUAGE] != None:
                    # remove line breaks of description since these break the comment blocks
                    dist["description"] = re.sub(r"[\n\r]+", " ", dist["description"][LANGUAGE])
                else:
                    dist["description"] = ""
            # get other metadata of distribution
            md = [f"# {k.capitalize():<25}: {dist.get(k, None)}\n" for k in KEYS_DISTRIBUTIONS]
            tmp_dists.append("".join(md))
            # in a few cases the dataset has no download_url but rather is available at "url"
            csv_url = dist.get("download_url", dist["url"])
            tmp_links.append(csv_url)
            
        # use .at[] – https://stackoverflow.com/a/53299945/7117003
        data.at[idx, "distributions"] = tmp_dists
        data.at[idx, "distribution_links"] = tmp_links
    
    # sort values for table
    data.sort_values(f"{SORT_TABLE_BY}", inplace=True)
    data.reset_index(drop=True, inplace=True)
    
    return data[REDUCED_FEATURESET]


def create_python_notebooks(data):
    """Create Jupyter Notebooks with Python starter code"""
    for idx in tqdm(data.index):
        # open template
        with open(f"{TEMPLATE_FOLDER}{TEMPLATE_PYTHON}") as file:
            py_nb = file.read()

        # populate template with metadata
        py_nb = py_nb.replace("{{ PROVIDER }}", PROVIDER)
        
        title = re.sub("\"", "\'", data.loc[idx, f"title.{LANGUAGE}"])
        py_nb = py_nb.replace("{{ DATASET_TITLE }}", title)
        
        description = data.loc[idx, f"description.{LANGUAGE}"]
        description = re.sub("\"", "\'", description)
        description = re.sub("\\\\", "|", description)
        py_nb = py_nb.replace("{{ DATASET_DESCRIPTION }}", description)
        
        py_nb = py_nb.replace("{{ DATASET_IDENTIFIER }}", data.loc[idx, "identifier"])        
        py_nb = py_nb.replace("{{ DATASET_METADATA }}", re.sub("\"", "\'", data.loc[idx, "metadata"]))          
        py_nb = py_nb.replace("{{ DISTRIBUTION_COUNT }}", str(len(data.loc[idx, "distributions"])))
        
        url = f'[Direct link by {PROVIDER} for dataset]({BASELINK_DATAPORTAL}{data.loc[idx, "name"]})'
        py_nb = py_nb.replace("{{ DATASHOP_LINK_PROVIDER }}", url)
        
        if data.loc[idx, "url"] != None:
            org_name = f"organization.display_name.{LANGUAGE}"
            url = data.loc[idx, "url"]
            url = f'[Direct link by {data.loc[idx, org_name]} for dataset]({url})'
            py_nb = py_nb.replace("{{ DATASHOP_LINK_ORGANIZATION }}", url)
        
        py_nb = py_nb.replace("{{ CONTACT }}", data.loc[idx, "contact"])

        py_nb = json.loads(py_nb, strict=False)
 
        # find code cell for dataset imports
        for id_cell, cell in enumerate(py_nb["cells"]):
            if cell["id"] == "0":
                dist_cell_idx = id_cell
                break
        # iterate over csv distributions and create metadata comments and code
        code_block = []
        for id_dist, (dist, dist_link) in enumerate(zip(data.loc[idx, "distributions"], data.loc[idx, "distribution_links"])):
            code = f"# Distribution {id_dist}\n{dist}\ndf = get_dataset('{dist_link}')\n"
            code = "".join([f'{line}\n' for line in code.split("\n")])
            code_block.append(code)
        # populate code block with data for all distributions
        code_block = "".join(code_block)
        py_nb["cells"][dist_cell_idx]["source"] =  code_block

        # save to disk
        with open(f'{TEMP_PREFIX}{REPO_PYTHON_OUTPUT}{data.loc[idx, "id"]}.ipynb', 'w') as file:
            file.write(json.dumps(py_nb))         


def create_rmarkdown(data):
    """Create R Markdown files with R starter code"""
    for idx in tqdm(data.index):
        # open template
        with open(f"{TEMPLATE_FOLDER}{TEMPLATE_RMARKDOWN}") as file:
            rmd = file.read()

        # populate template with metadata
        title = f"Open Government Data, {PROVIDER}"
        rmd = rmd.replace("{{ DOCUMENT_TITLE }}", title)
        
        title = re.sub("\"", "\'", data.loc[idx, f"title.{LANGUAGE}"])
        rmd = rmd.replace("{{ DATASET_TITLE }}", title)
      
        rmd = rmd.replace("{{ TODAY_DATE }}", TODAY_DATE)
        rmd = rmd.replace("{{ DATASET_IDENTIFIER }}", data.loc[idx, "identifier"])
        
        description = data.loc[idx, f"description.{LANGUAGE}"]
        description = re.sub("\"", "\'", description)
        description = re.sub("\\\\", "|", description)
        rmd = rmd.replace("{{ DATASET_DESCRIPTION }}", description)
        
        rmd = rmd.replace("{{ DATASET_METADATA }}", data.loc[idx, "metadata"])
        rmd = rmd.replace("{{ CONTACT }}", data.loc[idx, "contact"])
        rmd = rmd.replace("{{ DISTRIBUTION_COUNT }}", str(len(data.loc[idx, "distributions"])))
        
        url = f'[Direct link by **{PROVIDER}** for dataset]({BASELINK_DATAPORTAL}{data.loc[idx, "name"]})'
        rmd = rmd.replace("{{ DATASHOP_LINK_PROVIDER }}", url)
        
        if data.loc[idx, "url"] != None:
            org_name = f"organization.display_name.{LANGUAGE}"
            url = data.loc[idx, "url"]
            url = f'[Direct link by **{data.loc[idx, org_name]}** for dataset]({url})'
            rmd = rmd.replace("{{ DATASHOP_LINK_ORGANIZATION }}", url)
            
        # create code blocks for all distributions
        code_block = []
        for id_dist, (dist, dist_link) in enumerate(zip(data.loc[idx, "distributions"], data.loc[idx, "distribution_links"])):
            code = f"# Distribution {id_dist}\n{dist}\ndf <- read_delim('{dist_link}')\n\n"
            code_block.append(code)
        rmd = rmd.replace("{{ DISTRIBUTIONS }}", "".join(code_block))

        # save to disk
        with open(f'{TEMP_PREFIX}{REPO_RMARKDOWN_OUTPUT}{data.loc[idx, "id"]}.Rmd', 'w') as file:
            file.write("".join(rmd))

            
def get_header(dataset_count):
    """Retrieve header template and populate with date and count of data records"""
    with open(f"{TEMPLATE_FOLDER}{TEMPLATE_HEADER}") as file:
        header = file.read()
    gh_page = f"https://{GITHUB_ACCOUNT}.github.io/{REPO_NAME}/"
    header = re.sub("{{ GITHUB_PAGE }}", gh_page, header)
    
    gh_link = f"https://www.github.com/{GITHUB_ACCOUNT}/{REPO_NAME}"
    header = re.sub("{{ GITHUB_REPO }}", gh_link, header)
    
    header = re.sub("{{ PROVIDER }}", PROVIDER, header)
    header = re.sub("{{ DATA_PORTAL }}", PROVIDER_LINK, header)
    header = re.sub("{{ DATASET_COUNT }}", str(int(dataset_count)), header)
    header = re.sub("{{ TODAY_DATE }}", TODAY_DATETIME, header)
    return header


def create_readme(dataset_count):
    """Retrieve README template and populate with metadata"""
    with open(f"{TEMPLATE_FOLDER}{TEMPLATE_README}") as file:
        readme = file.read()
    readme = re.sub("{{ PROVIDER }}", PROVIDER, readme)
    readme = re.sub("{{ DATASET_COUNT }}", str(int(dataset_count)), readme)   
    readme = re.sub("{{ DATA_PORTAL }}", PROVIDER_LINK, readme)
    gh_page = f"https://{GITHUB_ACCOUNT}.github.io/{REPO_NAME}/"
    readme = re.sub("{{ GITHUB_PAGE }}", gh_page, readme)
    readme = re.sub("{{ TODAY_DATE }}", TODAY_DATETIME, readme)
    with open(f"{TEMP_PREFIX}README.md", "w") as file:
        file.write(readme)


def create_overview(data, header):
    """Create README with link table"""
    baselink_r_gh = f"https://github.com/{GITHUB_ACCOUNT}/{REPO_NAME}/blob/{REPO_BRANCH}/{REPO_RMARKDOWN_OUTPUT}/"
    baselink_py_gh = f"https://github.com/{GITHUB_ACCOUNT}/{REPO_NAME}/blob/{REPO_BRANCH}/{REPO_PYTHON_OUTPUT}/"
    baselink_py_colab = f"https://githubtocolab.com/{GITHUB_ACCOUNT}/{REPO_NAME}/blob/{REPO_BRANCH}/{REPO_PYTHON_OUTPUT}/"
    # baselink_py_kaggle = f"https://kaggle.com/kernels/welcome?src={baselink_py_gh}"

    md_doc = []
    md_doc.append(header)
    md_doc.append(f"| Title (abbreviated to {TITLE_MAX_CHARS} chars) | Python Colab | Python GitHub | R GitHub |\n")
    md_doc.append("| :-- | :-- | :-- | :-- |\n")

    for idx in tqdm(data.index):
        # remove square brackets from title, since these break markdown links
        title_clean = data.loc[idx, f"title.{LANGUAGE}"].replace("[", " ").replace("]", " ")
        if len(title_clean) > TITLE_MAX_CHARS:
            title_clean = title_clean[:TITLE_MAX_CHARS] + "…"

        ds_link = f'{BASELINK_DATAPORTAL}{data.loc[idx, "name"]}'
        filename = data.loc[idx, "id"]
        
        r_gh_link = f'[R GitHub]({baselink_r_gh}{filename}.Rmd)'
        
        py_gh_link = f'[Python GitHub]({baselink_py_gh}{filename}.ipynb)'
        py_colab_link = f'[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)]({baselink_py_colab}{filename}.ipynb)'
        # py_kaggle_link = f'[![Kaggle](https://kaggle.com/static/images/open-in-kaggle.svg)]({baselink_py_kaggle}{filename}.ipnyb)'
        
        md_doc.append(f"| [{title_clean}]({ds_link}) | {py_colab_link} | {py_gh_link} | {r_gh_link} |\n")

    md_doc = "".join(md_doc)

    with open(f"{TEMP_PREFIX}index.md", "w") as file:
        file.write(md_doc)


# CREATE CODE FILES --------------------------------------------------------------------------------------------------- # 

all_packages = get_full_package_list()

df = filter_csv(all_packages)
df = clean_features(df)

df = prepare_data_for_codebooks(df)

create_python_notebooks(df)
create_rmarkdown(df)

header = get_header(dataset_count=len(df))
create_readme(dataset_count=len(df))
create_overview(df, header)



































