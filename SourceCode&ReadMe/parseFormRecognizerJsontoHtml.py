from enum import Enum
from shapely.geometry import Polygon
import math
from itertools import groupby



DEF_PERCENT = 0.9

class ElementType(Enum):
    word = 1
    checkbox = 2

class ElementWeight(Enum):
    Word = 1
    Checkbox = 1.1

class Coordinates:
    def __init__(self, X: int, Y: int):
        self.X = X
        self.Y = Y

class VerticalInterval:
    def __init__(self, yMax: int, yMin: int):
        self.yMax = yMax
        self.yMin = yMin

class ElementSpan:
    def __init__(self, offset: int, length: int):
        self.offset = offset
        self.length = length

class BaseElement:
    def __init__(self, type: ElementType, weight: ElementWeight, content: str,
                 centerCoordinates: Coordinates, verticalInterval: VerticalInterval,
                 polygon: list[int]):
        self.type = type
        self.weight = weight
        self.content = content
        self.centerCoordinates = centerCoordinates
        self.verticalInterval = verticalInterval
        self.polygon = polygon


""""
 * Analysis each paragraph and parse it into JSX.Element
 * @param result the analyzeResult object in Ocrtoy json.
 * @returns JSX.Element to render
"""
def renderPage(result):
    paragraphs = result.paragraphs
    tables = result.tables
    pageContentArr = []
    for p in paragraphs:
        table = next((table for table in tables if any(cell.bounding_regions[0].polygon == p.bounding_regions[0].polygon for cell in table.cells)), None)
        if table:
            table.type = "table"
            if not any(content.bounding_regions[0].polygon == table.bounding_regions[0].polygon for content in pageContentArr):
                pageContentArr.append(table)
        else:
            p.type = "text"
            pageContentArr.append(p)
    return renderParagraphs(pageContentArr, result)



""""
 * parse the content into JSX.Element by each category
 * @param contentArr categorized content
 * @param result the analyzeResult object in Ocrtoy json.
 * @returns JSX.Element to render
"""
def renderParagraphs(contentArr, result):
    temp = []
    group_paragraphs = []
    for index, content in enumerate(contentArr):
        if content.type == "text":
            temp.append(content)
        else:
            if len(temp) > 0:
                group_paragraphs.append(temp)
            group_paragraphs.append(content)
            temp = []
        if index == len(contentArr) - 1 and len(temp) > 0:
            group_paragraphs.append(temp)

    output = []
    for content in group_paragraphs:
        if hasattr(content, "__len__") == False and content.type == "table":
            output.append(render_table(content, result))
        else:
           output.append(render_paragraph(content, result))

    return output

""""
 * render table content into JSX.Element
 * @param table content of table
 * @param result the analyzeResult object in Ocrtoy json.
 * @return JSX.Element to render
"""
def render_table(table, result):
    table_cells = table.cells
    html = "<table border='1' style='border-spacing: 0px; border-collapse: collapse;'>\n<tbody>\n"
    data_by_rows = groupby(table_cells, key=lambda cell: cell.row_index)

    for row_index,group in data_by_rows:
        html += "<tr>\n"
        for cell in group:
            content = parse_table_cell_content_to_html(cell, result)
            if cell.kind in ("columnHeader", "rowHeader"):
                html += f"<th rowSpan={cell.row_span} colSpan={cell.column_span}>\n{content}\n</th>\n"
            else:
                html += f"<td rowSpan={cell.row_span} colSpan={cell.column_span}>\n{content}\n</td>\n"
        html += "</tr>\n"
    html += "</tbody>\n</table>\n"
    return html

""""
 * render paragraphs content into JSX.Element
 * @param paragraphs content of paragraphs
 * @param result the analyzeResult object in Ocrtoy json.
 * @returns JSX.Element to render
"""
def render_paragraph(paragraphs, result):
    elements = []
    def_page = result.pages[0]
    words = [get_all_words_in_paragraph(paragraph, result) for paragraph in paragraphs]
    words = [v for sublist in words for v in sublist]
    words_polygon = get_polygon([word['polygon'] for word in words])
    selections_to_sort = [
        {
            'type': ElementType.checkbox,
            'content': select.state,
            'center_coordinates': calc_geometric_center_coordinates(select.polygon),
            'vertical_interval': pick_vertical_interval(select.polygon),
            'weight': 1.1,
            'polygon': select.polygon,
        }
        for select in def_page.selection_marks
        if intersection_in_percent(words_polygon, select.polygon)
    ]
    elements = output_html_by_base_elements(words + selections_to_sort)
    return elements


""""
 * calculate the total polygon of several words.
 * @param polygons the array of word's polygon
 * @returns the total polygon
"""
def get_polygon(polygons):
  x = [p[0].x for p in polygons] + [p[1].x for p in polygons] + [p[2].x for p in polygons] + [p[3].x for p in polygons]
  y = [p[0].y for p in polygons] + [p[1].y for p in polygons] + [p[2].y for p in polygons] + [p[3].y for p in polygons]
  min_x = min(x)
  max_x = max(x)
  min_y = min(y)
  max_y = max(y)

  return [min_x, min_y, max_x, min_y, max_x, max_y, min_x, max_y]

""""
 * parse the table cell object into JSX.Element
 * @param cellObj cell object in Ocrtoy result
 * @param result the analyzeResult object in Ocrtoy json.
 * @returns JSX.Element of cell object to render
"""
def parse_table_cell_content_to_html(cell_obj, result):
    elements = []
    if cell_obj and result:
        words_to_sort = get_all_words_in_paragraph(cell_obj, result)
        selections_to_sort = get_all_selections_in_cell(cell_obj, result)
        elements = output_html_by_base_elements(words_to_sort + selections_to_sort)

    return elements


""""
 * get all the selection box from cell object
 * @param cellObj cell object in Ocrtoy result
 * @param result the analyzeResult object in Ocrtoy json.
 * @returns selection boxes elements
"""
def get_all_selections_in_cell(cell_obj, result):
    selections = []
    def_page = result.pages[0]

    if def_page.selection_marks:
        selections = [select for select in def_page.selection_marks if any(span for span in cell_obj.spans if span.offset <= select.span.offset and select.span.offset + select.span.length <= span.offset + span.length)]

    selections_to_sort = [{
        'type': ElementType.checkbox,
        'content': select.state,
        'center_coordinates': calc_geometric_center_coordinates(select.polygon),
        'vertical_interval': pick_vertical_interval(select.polygon),
        'polygon': select.polygon,
        'weight': ElementWeight.Checkbox
    } for select in selections]

    return selections_to_sort

""""
 * get all the word elements from paragraph
 * @param para a paragraph object in Ocrtoy result
 * @param result the analyzeResult object in Ocrtoy json.
 * @returns word elements
"""
def get_all_words_in_paragraph(para, result):
    all_words = []
    if para and para.spans and result.pages and result.pages[0]:
        def_page = result.pages[0]
        if para.spans and len(para.spans) > 0:
            para_span = para.spans[0]
            cell_content_start_index = para_span.offset
            cell_content_end_index = para_span.offset + para_span.length

            all_words = [{ 
                    "type": ElementType.word,
                    "weight": ElementWeight.Word,
                    "content": w.content,
                    "center_coordinates": calc_geometric_center_coordinates(w.polygon),
                    "vertical_interval": pick_vertical_interval(w.polygon),
                    "polygon": w.polygon
                }
                for w in def_page.words
                if cell_content_start_index <= w.span.offset
                and w.span.offset + w.span.length <= cell_content_end_index
            ]
    return all_words

""""
 * render each base element by it's type
 * @param elementArr base element to render
 * @returns the Jsx.Element result
"""
def renderHtmlElement(elementArr):
    transformedEleArr = []
    for ele in elementArr:
        if ele['type'] == ElementType.word:
            transformedEleArr.append(ele['content'])
        elif ele['type'] == ElementType.checkbox:
            if ele['content'] == "selected":
                transformedEleArr.append(f'<input type="checkbox" checked="true"></input>')
            else: 
                transformedEleArr.append(f'<input type="checkbox"></input>')
    
    strBuffer = ""
    jsxEleArr = []
    for index, ele in enumerate(transformedEleArr):
        if type(ele) is str:
            strBuffer += ele + " "
        else:
            if strBuffer:
                jsxEleArr.append(f'{strBuffer}')
            jsxEleArr.append(ele)
            strBuffer = ""
        
        if strBuffer and index == len(transformedEleArr) - 1:
            jsxEleArr.append(f'{strBuffer}')
    
    return jsxEleArr

""""
 * Sort the base elements and render them into JSX.Element array.
 * @param baseElements
 * @returns sorted JSX.Element array
"""
def output_html_by_base_elements(baseElements):
    groupMap = {}
    for ele in baseElements:
        findSameLine = False
        for yKey, eleArr in groupMap.items():
            lastElement = eleArr[-1]
            isSameLine = check_vertical_interval_intersection_in_percent(
                lastElement['vertical_interval'],
                ele['vertical_interval'],
                0.7
            )
            if isSameLine:
                eleArr.append(ele)
                groupMap[yKey] = eleArr
                findSameLine = True
                break
        if not findSameLine:
            groupMap[(ele['vertical_interval']['yMax'] + ele['vertical_interval']['yMin']) / 2] = [ele]

    ySortedElementsArr = sorted(groupMap.items(), key=lambda x: x[0])

    htmlElements = []
    for _, eleArr in ySortedElementsArr:
        xSortedElements = sorted(eleArr, key=lambda x: x['center_coordinates']['X'] if x['center_coordinates']['X'] != 0 else x['weight'], reverse=True)
        if len(ySortedElementsArr) == 1:
            htmlElements.append(renderHtmlElement(xSortedElements))
        else:
            htmlElements.append("<p>{}</p>".format(renderHtmlElement(xSortedElements)))


""""
 * parse polygon into truf position
 * @param boundingBox polygon
 * @returns turf position
"""
def boundingBoxToPosition(boundingBox):
    if hasattr(boundingBox[0], 'x'): 
      return Polygon([
          (boundingBox[0].x, boundingBox[0].y),
          (boundingBox[1].x, boundingBox[1].y),
          (boundingBox[2].x, boundingBox[2].y),
          (boundingBox[3].x, boundingBox[3].y)
          ])

    return Polygon([
        (boundingBox[0], boundingBox[1]),
        (boundingBox[2], boundingBox[3]),
        (boundingBox[4], boundingBox[5]),
        (boundingBox[6], boundingBox[7])
        ])


""""
 * calculate whether two area of polygon coincide over specific percent
 * @param polygon1 polygon 1
 * @param polygon2 polygon 2
 * @param percent threshold in percent
 * @returns is coincide or not
"""
def intersection_in_percent(polygon1, polygon2, percent=DEF_PERCENT):
    poly1 = boundingBoxToPosition(polygon1)
    poly2 = boundingBoxToPosition(polygon2)

    # Calculate the area of the intersection between the two polygons
    intersection_area = poly1.intersection(poly2).area

    # Calculate the percent overlap of the two polygons
    percent_overlap = (intersection_area / poly1.area) * 100

    # Check if the percent overlap is greater than or equal to the minimum required
    if percent_overlap >= percent:
        print("The two polygons coincide.")
        return True
    else:
        print("The two polygons do not coincide.")
        return False 


""""
 * get the vertical interval from polygon
 * @param polygon object polygon
 * @returns vertical interval
"""
def pick_vertical_interval(polygon):
    yArr = sorted([polygon[0].y, polygon[1].y, polygon[2].y, polygon[3].y])
    return {
        'yMax': yArr[3],
        'yMin': yArr[0]
    }

""""
 * checks if two vertical intervals coincide in specific percent
 * @param a vertical interval
 * @param b vertical interval
 * @returns is coincide or not
"""
def check_vertical_interval_intersection_in_percent(a, b, threshold_in_percent):
    common_ymax = float('NaN')
    common_ymin = float('NaN')
    if b['yMin'] < a['yMax'] and a['yMax'] <= b['yMax']:
        common_ymax = a['yMax']
        common_ymin = a['yMin'] if a['yMin'] >= b['yMin'] else b['yMin']
    elif a['yMin'] < b['yMax'] and b['yMax'] <= a['yMax']:
        common_ymax = b['yMax']
        common_ymin = b['yMin'] if b['yMin'] >= a['yMin'] else a['yMin']

    if math.isnan(common_ymax) and math.isnan(common_ymin):
        return False

    common_len = common_ymax - common_ymin
    return (
        common_len / (a['yMax'] - a['yMin']) > threshold_in_percent or
        common_len / (b['yMax'] - b['yMin']) > threshold_in_percent
    )

""""
 * calculate geometric center coordinates from polygon
 * @param polygon object polygon
 * @returns geometric center coordinates
"""
def calc_geometric_center_coordinates(polygon):
  x1 = polygon[0].x
  y1 = polygon[0].y
  x3 = polygon[2].x
  y3 = polygon[2].y

  return {'X': x3 - (x3 - x1) / 2, 'Y': y3 - (y3 - y1) / 2}
#endregion

""""
 * parse Ocrtoy result json into html
 * @param jsonStirng the json result of Ocrtoy
 * @returns Html string.
"""
def parseOcrJsonToHtml(jsonString):
    obj = json.loads(jsonString)
    element = ""
    if obj["status"] == "succeeded":
        element = renderPage(obj["analyzeResult"])

    return element