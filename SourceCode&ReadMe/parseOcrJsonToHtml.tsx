import _ from "lodash";
import * as turf from "@turf/turf";
import { renderToString } from "react-dom/server";

//#region  type define
enum ElementType {
  word,
  checkbox,
}
enum ElementWeight {
  Word = 1,
  Checkbox = 1.1,
}

interface coordinates {
  X: number;
  Y: number;
}

interface verticalInterval {
  yMax: number;
  yMin: number;
}

interface elementSpan {
  offset: number;
  length: number;
}

interface baseElement {
  type: ElementType;
  weight: ElementWeight;
  content: string;
  centerCoordinates: coordinates;
  verticalInterval: verticalInterval;
  polygon: number[];
}
//#endregion

//#region handling elements

/**
 * Analysis each paragraph and parse it into JSX.Element
 * @param result the analyzeResult object in Ocrtoy json.
 * @returns JSX.Element to render
 */
const renderPage = (result: any) => {
  const paragraphs = result["paragraphs"];
  const tables = result["tables"];
  let pageContentArr: any[] = [];
  paragraphs.forEach((p: any) => {
    const table = tables.find((table: any) =>
      table["cells"].some((cell: any) =>
        _.isEqual(
          cell["boundingRegions"][0]["polygon"],
          p["boundingRegions"][0]["polygon"]
        )
      )
    );
    if (table) {
      table["type"] = "table";
      if (
        !pageContentArr.find((content: any) =>
          _.isEqual(
            table["boundingRegions"][0]["polygon"],
            content["boundingRegions"][0]["polygon"]
          )
        )
      ) {
        pageContentArr.push(table);
      }
    } else {
      p["type"] = "text";
      pageContentArr.push(p);
    }
  });
  return renderParagraphs(pageContentArr, result);
};

/**
 * parse the content into JSX.Element by each category
 * @param contentArr categorized content
 * @param result the analyzeResult object in Ocrtoy json.
 * @returns JSX.Element to render
 */
const renderParagraphs = (contentArr: any[], result: any) => {
  let temp: any[] = [];
  let group_paragraphs: any = [];
  contentArr.forEach((content: any, index: number) => {
    if (content["type"] === "text") {
      temp.push(content);
    } else {
      if (temp.length > 0) {
        group_paragraphs.push(temp);
      }
      group_paragraphs.push(content);
      temp = [];
    }
    if (index === contentArr.length - 1 && temp.length > 0) {
      group_paragraphs.push(temp);
    }
  });
  return (
    <>
      {group_paragraphs.map((content: any) => {
        if (content["type"] === "table") {
          return renderTable(content, result);
        } else {
          return renderParagraph(content, result);
        }
      })}
    </>
  );
};

/**
 * render table content into JSX.Element
 * @param table content of table
 * @param result the analyzeResult object in Ocrtoy json.
 * @return JSX.Element to render
 */
const renderTable = (table: any, result: any) => {
  const table_cells = table["cells"];
  return (
    <table
      border={1}
      style={{
        borderSpacing: "0px",
        borderCollapse: "collapse",
      }}
    >
      <tbody>
        {_.map(_.groupBy(table_cells, (cell: any) => cell.rowIndex)).map(
          (rows: any, rowIndex: number) => {
            return (
              <tr key={rowIndex}>
                {rows.map((cell: any, cellIndex: number) => {
                  const content = parseTableCellContentToHtml(cell, result);
                  if (
                    cell["kind"] === "columnHeader" ||
                    cell["kind"] === "rowHeader"
                  ) {
                    return (
                      <th
                        key={cellIndex}
                        rowSpan={cell.rowSpan}
                        colSpan={cell.columnSpan}
                      >
                        {content}
                      </th>
                    );
                  } else {
                    return (
                      <td
                        key={cellIndex}
                        rowSpan={cell.rowSpan}
                        colSpan={cell.columnSpan}
                      >
                        {content}
                      </td>
                    );
                  }
                })}
              </tr>
            );
          }
        )}
      </tbody>
    </table>
  );
};

/**
 * render paragraphs content into JSX.Element
 * @param paragraphs content of paragraphs
 * @param result the analyzeResult object in Ocrtoy json.
 * @returns JSX.Element to render
 */
const renderParagraph = (paragraphs: any, result: any) => {
  let elements = [<></>];
  const defPage = result.pages[0];
  const words = paragraphs
    .map((paragraph: any) => {
      return getAllWordsInParagraph(paragraph, result);
    })
    .flatMap((v: any) => v);

  const wordsPolygon = getPolygon(words.map((word: any) => word.polygon));

  const selectionsToSort: baseElement[] = (defPage.selectionMarks || [])
    .filter((select: any) =>
      intersectionInPercent(wordsPolygon, select.polygon)
    )
    .map((select: any) => {
      const coordinates = calcGeometricCenterCoordinates(
        select.polygon as number[]
      );
      const vInterval = pickVerticalInterval(select.polygon as number[]);
      return {
        type: ElementType.checkbox,
        content: select.state,
        centerCoordinates: coordinates,
        verticalInterval: vInterval,
        weight: 1.1,
        polygon: select.polygon,
      } as baseElement;
    });

  elements = outputHtmlByBaseElements([...words, ...selectionsToSort]);

  return elements;
};

/**
 * calculate the total polygon of several words.
 * @param polygons the array of word's polygon
 * @returns the total polygon
 */
const getPolygon = (polygons: number[][]) => {
  const x = polygons.map((p) => [p[0], p[2], p[4], p[6]]).flatMap((x) => x);
  const y = polygons.map((p) => [p[1], p[3], p[5], p[7]]).flatMap((y) => y);
  const MinX = Math.min(...x);
  const MaxX = Math.max(...x);
  const MinY = Math.min(...y);
  const MaxY = Math.max(...y);

  return [MinX, MinY, MaxX, MinY, MaxX, MaxY, MinX, MaxY];
};

/**
 * parse the table cell object into JSX.Element
 * @param cellObj cell object in Ocrtoy result
 * @param result the analyzeResult object in Ocrtoy json.
 * @returns JSX.Element of cell object to render
 */
const parseTableCellContentToHtml = (cellObj: any, result: any) => {
  let elements = [<></>];
  if (cellObj && result) {
    const wordsToSort = getAllWordsInParagraph(cellObj, result);
    const selectionsToSort = getAllSelectionsInCell(cellObj, result);
    elements = outputHtmlByBaseElements([...wordsToSort, ...selectionsToSort]);
  }
  return elements;
};

/**
 * get all the selection box from cell object
 * @param cellObj cell object in Ocrtoy result
 * @param result the analyzeResult object in Ocrtoy json.
 * @returns selection boxes elements
 */
const getAllSelectionsInCell = (cellObj: any, result: any) => {
  let selections: any[] = [];
  const defPage = result.pages[0];

  if (defPage.selectionMarks) {
    selections = defPage.selectionMarks.filter((select: any) => {
      const cellSelectionSpans = _.cloneDeep(cellObj.spans) as elementSpan[];
      return cellSelectionSpans.some((span) => {
        const selectSpan = select.span as elementSpan;
        return (
          span.offset <= selectSpan.offset &&
          selectSpan.offset + selectSpan.length <= span.offset + span.length
        );
      });
    });
  }

  const selectionsToSort: baseElement[] = selections.map((select: any) => {
    const coordinates = calcGeometricCenterCoordinates(
      select.polygon as number[]
    );

    const vInterval = pickVerticalInterval(select.polygon as number[]);

    return {
      type: ElementType.checkbox,
      content: select.state,
      centerCoordinates: coordinates,
      verticalInterval: vInterval,
      polygon: select.polygon,
      weight: ElementWeight.Checkbox,
    } as baseElement;
  });

  return selectionsToSort;
};

/**
 * get all the word elements from paragraph
 * @param para a paragraph object in Ocrtoy result
 * @param result the analyzeResult object in Ocrtoy json.
 * @returns word elements
 */
const getAllWordsInParagraph = (para: any, result: any) => {
  let allWords: baseElement[] = [];
  if (para && para.spans && result.pages && result.pages[0]) {
    const defPage = result.pages[0];
    if (para.spans && para.spans.length > 0) {
      const paraSpan = para.spans[0];
      const cellContentStartIndex = paraSpan.offset;
      const cellContentEndIndex = paraSpan.offset + paraSpan.length;

      allWords = defPage.words
        .filter(
          (w: any) =>
            cellContentStartIndex <= w.span.offset &&
            w.span.offset + w.span.length <= cellContentEndIndex
        )
        .map((w: any) => {
          const coordinates = calcGeometricCenterCoordinates(
            w.polygon as number[]
          );
          const vInterval = pickVerticalInterval(w.polygon as number[]);

          return {
            type: ElementType.word,
            weight: ElementWeight.Word,
            content: w.content,
            centerCoordinates: coordinates,
            verticalInterval: vInterval,
            polygon: w.polygon,
          } as baseElement;
        });
    }
  }

  return allWords;
};

/**
 * render each base element by it's type
 * @param elementArr base element to render
 * @returns the Jsx.Element result
 */
const renderHtmlElement = (elementArr: baseElement[]) => {
  const transformedEleArr = elementArr.map((ele) => {
    switch (ele.type) {
      case ElementType.word: {
        return ele.content as string;
      }
      case ElementType.checkbox: {
        return (
          <input
            type="checkbox"
            checked={ele.content === "selected"}
            onChange={() => {}}
          ></input>
        );
      }
      default: {
        return "";
      }
    }
  });

  let strBuffer = "";
  const jsxEleArr: JSX.Element[] = [];
  transformedEleArr.forEach((ele, index, arr) => {
    if (typeof ele === "string") {
      strBuffer += ele + " ";
    } else {
      strBuffer && jsxEleArr.push(<>{strBuffer}</>);
      jsxEleArr.push(ele);
      strBuffer = "";
    }

    if (strBuffer && index === arr.length - 1) {
      strBuffer && jsxEleArr.push(<>{strBuffer}</>);
    }
  });

  return jsxEleArr;
};

/**
 * Sort the base elements and render them into JSX.Element array.
 * @param baseElements
 * @returns sorted JSX.Element array
 */
const outputHtmlByBaseElements = (baseElements: baseElement[]) => {
  const groupMap = new Map<Number, baseElement[]>();
  baseElements.forEach((ele) => {
    const findSameLine = Array.from(groupMap).some(([yKey, eleArr]) => {
      const lastElement = eleArr[eleArr.length - 1];
      const isSameLine = checkVerticalIntervalIntersectionInPercent(
        lastElement.verticalInterval,
        ele.verticalInterval,
        0.7
      );
      if (isSameLine) {
        eleArr.push(ele);
        groupMap.set(yKey, eleArr);
      }

      return isSameLine;
    });

    if (!findSameLine) {
      groupMap.set(
        (ele.verticalInterval.yMax + ele.verticalInterval.yMin) / 2,
        [ele]
      );
    }
  });

  const ySortedElementsArr = Array.from(groupMap).sort(
    (a, b) => (a[0] as number) - (b[0] as number)
  );

  return ySortedElementsArr.map(([_, eleArr]) => {
    const xSortedElements: baseElement[] = eleArr.sort((a, b) => {
      const diff: number = a.centerCoordinates.X - b.centerCoordinates.X;
      if (diff === 0) {
        return b.weight - a.weight;
      }
      return diff;
    });

    if (ySortedElementsArr.length === 1) {
      return <>{renderHtmlElement(xSortedElements)}</>;
    } else {
      return <p>{renderHtmlElement(xSortedElements)}</p>;
    }
  });
};
//#endregion

//#region common function

/**
 * parse polygon into truf position
 * @param boundingBox polygon
 * @returns turf position
 */
const boundingBoxToPosition = (boundingBox: number[]) => {
  return [
    [boundingBox[0], boundingBox[1]],
    [boundingBox[2], boundingBox[3]],
    [boundingBox[4], boundingBox[5]],
    [boundingBox[6], boundingBox[7]],
  ];
};

const DEF_PERCENT = 0.9;
/**
 * calculate whether two area of polygon coincide over specific percent
 * @param polygon1 polygon 1
 * @param polygon2 polygon 2
 * @param percent threshold in percent
 * @returns is coincide or not
 */
const intersectionInPercent = (
  polygon1: number[],
  polygon2: number[],
  percent: number = DEF_PERCENT
) => {
  const position1 = boundingBoxToPosition(polygon1);
  const position2 = boundingBoxToPosition(polygon2);

  const intersectP = turf.intersect(
    turf.polygon([position1.concat([position1[0]])]),
    turf.polygon([position2.concat([position2[0]])])
  );
  if (!intersectP) {
    return false;
  }

  const intersectArea = turf.area(intersectP);
  const area1 = turf.area(turf.polygon([position1.concat([position1[0]])]));
  const area2 = turf.area(turf.polygon([position2.concat([position2[0]])]));

  const areaPer1 = intersectArea / area1;
  const areaPer2 = intersectArea / area2;

  return areaPer1 > percent || areaPer2 > percent;
};

/**
 * get the vertical interval from polygon
 * @param polygon object polygon
 * @returns vertical interval
 */
const pickVerticalInterval = (polygon: number[]) => {
  const yArr = [polygon[1], polygon[3], polygon[5], polygon[7]].sort(
    (a, b) => a - b
  );

  return {
    yMax: yArr[3],
    yMin: yArr[0],
  };
};

/**
 * checks if two vertical intervals coincide in specific percent
 * @param a vertical interval
 * @param b vertical interval
 * @returns is coincide or not
 */
const checkVerticalIntervalIntersectionInPercent = (
  a: verticalInterval,
  b: verticalInterval,
  thresholdInPercent: number
) => {
  let commonYmax = NaN;
  let commonYmin = NaN;
  if (b.yMin < a.yMax && a.yMax <= b.yMax) {
    commonYmax = a.yMax;
    commonYmin = a.yMin >= b.yMin ? a.yMin : b.yMin;
  } else if (a.yMin < b.yMax && b.yMax <= a.yMax) {
    commonYmax = b.yMax;
    commonYmin = b.yMin >= a.yMin ? b.yMin : a.yMin;
  }

  if (isNaN(commonYmax) && isNaN(commonYmin)) {
    return false;
  }

  const commonLen = commonYmax - commonYmin;
  return (
    commonLen / (a.yMax - a.yMin) > thresholdInPercent ||
    commonLen / (b.yMax - b.yMin) > thresholdInPercent
  );
};

/**
 * calculate geometric center coordinates from polygon
 * @param polygon object polygon
 * @returns geometric center coordinates
 */
const calcGeometricCenterCoordinates = (polygon: number[]) => {
  const x1 = polygon[0];
  const y1 = polygon[1];
  const x3 = polygon[4];
  const y3 = polygon[5];

  return { X: x3 - (x3 - x1) / 2, Y: y3 - (y3 - y1) / 2 } as coordinates;
};
//#endregion

/**
 * parse Ocrtoy result json into html
 * @param jsonStirng the json result of Ocrtoy
 * @returns Html string.
 */
export const parseOcrJsonToHtml = (jsonStirng: string) => {
  const obj = JSON.parse(jsonStirng);
  let element = <></>;
  if (obj["status"] === "succeeded") {
    element = renderPage(obj["analyzeResult"]);
  }
  return renderToString(element);
};
