from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient
import os


def colorprint(txt,opt="222",end='\n'): 
    #print(f'\033[{opt}m',txt,'\033[0m',end=end)
    print(u"\u001b[38;5;"+opt+'m'+txt+u"\u001b[0m",end=end)

PAGES_PER_EMBEDDINGS = int(os.getenv('PAGES_PER_EMBEDDINGS', 2))
SECTION_TO_EXCLUDE = ['title', 'sectionHeading', 'footnote', 'pageHeader', 'pageFooter', 'pageNumber']

def analyze_read(formUrl,verbose =False ):

    
    document_analysis_client = DocumentAnalysisClient(
        endpoint=os.environ['FORM_RECOGNIZER_ENDPOINT'], credential=AzureKeyCredential(os.environ['FORM_RECOGNIZER_KEY'])
    )
    
    poller = document_analysis_client.begin_analyze_document_from_url(
            "prebuilt-layout", formUrl)
    layout = poller.result()

    if verbose:
        print('Extracted dictionary with keys: ', end='')
        print(layout.to_dict().keys())
        print('EXTRACTING:')

    results = []
    page_result = ''
    if verbose:print('paragraphs')
    for p in layout.paragraphs:
        if verbose:print('.',end='')
        page_number = p.bounding_regions[0].page_number
        output_file_id = int((page_number - 1 ) / PAGES_PER_EMBEDDINGS)

        if len(results) < output_file_id + 1:
            results.append('')

        if p.role not in SECTION_TO_EXCLUDE:
            results[output_file_id] += f"{p.content}\n"
    if verbose:print('\ntables')
    for t in layout.tables:
        if verbose:print('.',end='')
        page_number = t.bounding_regions[0].page_number
        output_file_id = int((page_number - 1 ) / PAGES_PER_EMBEDDINGS)
        
        if len(results) < output_file_id + 1:
            results.append('')
        previous_cell_row=0
        rowcontent='| '
        tablecontent = ''
        for c in t.cells:
            if c.row_index == previous_cell_row:
                rowcontent +=  c.content + " | "
            else:
                tablecontent += rowcontent + "\n"
                rowcontent='|'
                rowcontent += c.content + " | "
                previous_cell_row += 1
        results[output_file_id] += f"{tablecontent}|"
    if verbose:print()
    return results
#_____________________________________________________________________________________________________________________________

def format_table(t):
        results=[]
        page_number = t.bounding_regions[0].page_number
        output_file_id = int((page_number - 1 ) / PAGES_PER_EMBEDDINGS)
        
        if len(results) < output_file_id + 1:
            results.append('')
        previous_cell_row=0
        rowcontent='| '
        tablecontent = ''
        for c in t.cells:
            if c.row_index == previous_cell_row:
                rowcontent +=  c.content + " | "
            else:
                tablecontent += rowcontent + "\n"
                rowcontent='|'
                rowcontent += c.content + " | "
                previous_cell_row += 1
        results[output_file_id] += f"{tablecontent}|"
    
        return results


def format_bounding_region(bounding_regions):
    if not bounding_regions:
        return "N/A"
    return ", ".join("Page #{}: {}".format(region.page_number, format_polygon(region.polygon)) for region in bounding_regions)

def format_polygon(polygon):
    if not polygon:
        return "N/A"
    return ", ".join(["[{}, {}]".format(p.x, p.y) for p in polygon])



def analyze_general_documents(docUrl,verbose=False):
    kv_results=[]
    kv_dict={}
    document_analysis_client = DocumentAnalysisClient(
        endpoint=os.environ['FORM_RECOGNIZER_ENDPOINT'], credential=AzureKeyCredential(os.environ['FORM_RECOGNIZER_KEY'])
    )
    poller = document_analysis_client.begin_analyze_document_from_url(
            "prebuilt-document", docUrl)
    result = poller.result()

    for style in result.styles:
        if style.is_handwritten:
            print("Document contains handwritten content: ")
            print(",".join([result.content[span.offset:span.offset + span.length] for span in style.spans]))

    colorprint("----Key-value pairs found in document----")
    for kv_pair in result.key_value_pairs:
        try:
            kv_dict[kv_pair.key.content]=kv_pair.value.content
            kv_results.append(str(kv_pair.key.content)+' '+str(kv_pair.value.content))
        except: print('nothing found')
        if kv_pair.key:
            if verbose:
                print(
                        "Key '{}' found within '{}' bounding regions".format(
                            kv_pair.key.content,
                            format_bounding_region(kv_pair.key.bounding_regions),
                        )
                    )
        if kv_pair.value:
            if verbose:
                print(
                        "Value '{}' found within '{}' bounding regions\n".format(
                            kv_pair.value.content,
                            format_bounding_region(kv_pair.value.bounding_regions),
                        )
                    )
    raw_text_lines=[]
    raw_text_words=''
    for page in result.pages:
        colorprint("----Analyzing document from page #{}----".format(page.page_number))
        print(
            "Page has width: {} and height: {}, measured with unit: {}".format(
                page.width, page.height, page.unit
            )
        )
        
        for line_idx, line in enumerate(page.lines):
            raw_text_lines.append(line.content)
            if verbose:
                print(
                "...Line # {} has text content '{}' within bounding box '{}'".format(
                    line_idx,
                    line.content,
                    format_polygon(line.polygon),
                    )
                )
        #print(raw_text_lines)
        for word in page.words:
            raw_text_words+=f" {word.content}"
            if verbose:
                print(
                    "...Word '{}' has a confidence of {}".format(
                        word.content, word.confidence
                    )
                )
        checkbox=[]
        for selection_mark in page.selection_marks:
            if verbose:
                print(
                    "...Selection mark is '{}' within bounding box '{}' and has a confidence of {}".format(
                        selection_mark.state,
                        format_polygon(selection_mark.polygon),
                        selection_mark.confidence,
                    )
                )
            if selection_mark.state=='selected':
                checkbox.append([selection_mark.state,
                        format_polygon(selection_mark.polygon),
                        selection_mark.confidence,])

    table_text=[]
    for table_idx, table in enumerate(result.tables):
        
        '''
        print(
            "Table # {} has {} rows and {} columns".format(
                table_idx, table.row_count, table.column_count
            )
        )
        for region in table.bounding_regions:
            print(
                "Table # {} location on page: {} is {}".format(
                    table_idx,
                    region.page_number,
                    format_polygon(region.polygon),
                )
            )
        for cell in table.cells:
            print(
                "...Cell[{}][{}] has content '{}'".format(
                    cell.row_index,
                    cell.column_index,
                    cell.content,
                )
            )
            for region in cell.bounding_regions:
                print(
                    "...content on page {} is within bounding box '{}'\n".format(
                        region.page_number,
                        format_polygon(region.polygon),
                    )
                )
        '''
        table_text.append(format_table(table))
    print('-----------------------------------------------------------------------------')
    with open('context_data/FR_general.txt', 'w') as f:
            f.write(str(result) ) # text has to be string not a list
            
    return([kv_results,raw_text_lines,raw_text_words,table_text,checkbox,kv_dict])
   
