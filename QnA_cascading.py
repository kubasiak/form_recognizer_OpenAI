from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.storage.blob import BlobServiceClient, generate_blob_sas
from datetime import datetime, timedelta
import os,json
from dotenv import load_dotenv
from utilities.azureblobstorage import get_all_files
from utilities.utils import initialize, get_openAI_response
from utilities.utils import colorprint
from utilities.formrecognizer import analyze_read,analyze_general_documents
from urllib.parse import *
import tiktoken
from openai.embeddings_utils import get_embedding, cosine_similarity
import openai 
import time
import pandas as pd


load_dotenv()
account_name = os.environ['BLOB_ACCOUNT_NAME']
account_key = os.environ['BLOB_ACCOUNT_KEY']
connect_str = f"DefaultEndpointsProtocol=https;AccountName={account_name};AccountKey={account_key};EndpointSuffix=core.windows.net"
container_name = os.environ['BLOB_CONTAINER_NAME']
model = os.environ['OPENAI_QnA_MODEL'] #e.g. 'text-davinci-003' deployment
os.makedirs('data', mode = 0o777, exist_ok = True) 

def get_context_general(formUrl,file_name):
    file_name_root = os.path.splitext(file_name)[0] 
    context_file_name = os.path.join('data','context_'+file_name_root+'.txt') 
    colorprint('ANALYZING FILE : '+ file_name)
    colorprint('Sending the document to Form Recognizer to extract content')
    #file_sas = generate_blob_sas(account_name, container_name, file_name, account_key= account_key, permission='r', expiry=datetime.utcnow() + timedelta(hours=1))
    #formUrl=f"https://{account_name}.blob.core.windows.net/{container_name}/{quote(file_name)}?{file_sas}" 
    analysis_result=analyze_general_documents(formUrl)
    kv_text = analysis_result[0]
    raw_text_lines=analysis_result[1]
    raw_text_words=analysis_result[2]
    tables_text=analysis_result[3]
    checkbox=analysis_result[4]
    kv_dict=analysis_result[5]
    context=''
    context2=''
    for t in kv_text:
        if not ':unselected:' in t:  context = context+'\n'+t # for future use in prompt
    for t in checkbox:
        try:
            context = context+'\n'+''.join(str(t))
        except: 
            colorprint(str(type(t)),'99')
            print(t)
    for t in raw_text_lines:
        if t: context2 = context2+'\n'+t
    for t in tables_text:
        context2 = context2+'\n'+''.join(str(t))

    print(f"\nUnused context:\n{context2}")
         
    return(context,context2)

##############################################################################
with open('question.txt') as f:
    question = f.read().splitlines()
f.close()
colorprint('THE QUESTION: ' + str(question), '44')
colorprint('INITIALIZING OPENAI CONNECTION')
initialize()

df = pd.DataFrame(question[1:],columns =['Q'])

colorprint('DISCOVERING ALL FILES IN THE BLOB STORAGE:')
files_data = get_all_files()
files_data = list(map(lambda x: {'filename': x['filename']}, files_data))
for fd in files_data:
        print(fd['filename'])

file_name = files_data[1]['filename']
for file in files_data[0:4]:
    file_name=file['filename']
    
    file_name_root = os.path.splitext(file_name)[0] 
    context_file_name = os.path.join('context_data','context_'+file_name_root+'.txt') 
    context2_file_name = os.path.join('context_data','context2_'+file_name_root+'.txt') 
    
    try: 
        with open(context_file_name) as f:
            used_context =f.read()
            colorprint(f"Found file {context_file_name} with extracted content for context.      ------>     Reading file, NOT sending document to Form Recognizer.",'87')
        with open(context2_file_name) as f:
            secondary_context =f.read()
            colorprint(f"Found file {context2_file_name} with extracted content for context.     ------>     Reading file, NOT sending document to Form Recognizer.",'87')

    except:
        file_sas = generate_blob_sas(account_name, container_name, file_name, account_key= account_key, permission='r', expiry=datetime.utcnow() + timedelta(hours=1))
        formUrl=f"https://{account_name}.blob.core.windows.net/{container_name}/{quote(file_name)}?{file_sas}" 
    
        context = get_context_general(formUrl,file_name)
        used_context=context[0]
        secondary_context=context[1]
        with open(context_file_name, 'w') as f:
            f.write(used_context)  # text has to be string not a list
            colorprint(f"Writing context file {context_file_name}",'44')
        with open(context2_file_name, 'w') as f:
            f.write(secondary_context)  # text has to be string not a list
            colorprint(f"Writing context file {context2_file_name}",'44')

    #print(context2)
    try:
        openAIresponse = get_openAI_response(context=used_context,secondary_context=str(secondary_context),question=question,model=model,temperature =0.0, tokens_response=15,restart_sequence='\n\n')
        question_text = openAIresponse[0]
        response_text = openAIresponse[1]

        response_file_name =os.path.join('data','response_'+file_name_root+'.txt')
        with open(response_file_name, 'w') as f2:
            f2.write(str(response_text))  
        df[file_name_root]=response_text
    except:
        colorprint("File couldn't be processed",'9')

print(df)
