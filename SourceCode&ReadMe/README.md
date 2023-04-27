## Intro
The prototype that parse the ocrtoy result json to html, is implemented by Javascript. There is a function named ***parseOcrJsonToHtml***, recieve the ocr json as param and return the html element.

Sample code:

*const htmlString = parseOcrJsonToHtml(ocrJsonString);*

*console.log(htmlString);*

## Dev environment intergation:

1. (option:A)due to these function depandancy on some third party npm package. So need to copy add these package depandancy into package.json first

*"dependencies": {*

*"@turf/turf": "^6.5.0",*

*"@types/lodash": "^4.14.192",*

*"@types/react": "^18.0.28",*

*"@types/react-dom": "^18.0.11",*

*"react": "^18.2.0",*

*"react-dom": "^18.2.0",*

*"typescript": "^4.9.5"*

*}*

then run the "*npm install*" in terminal.

or

(option:B) run "*npm install --save typescript @turf/turf @types/lodash @types/react @types/react-dom react react-dom*" in terminal

2. just use the ***parseOcrJsonToHtml*** function by your program logic.

