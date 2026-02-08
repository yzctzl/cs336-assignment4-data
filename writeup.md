## look_at_cc
a. this page is http://0371rykj.com/ipfhsb/34.html, and is not accessable now, the content of this page is a production introduction page.

b. filter by title/h1/p/li/... tags, this text is low quality, only one continous sentence in the full page, most of the text are independent phrase, and has a harmful title. what is `恒溫恒濕試驗箱` and the structure of production information page, probably.

c. Yes. this example would be useful in training DOM Understanding and B2B SEO/SEO spam detection, would be useless in training conversational AI or natural language understanding systems.

d. Chinese/English/Dutch/Greek, Bussiness/Adult/Blog/Library/Politics/..., after about 70+ pages i seen a high-quality webpage.

## extract_text

b. text extracted by my function is not well formated and has many tags like th/ul/.. not removed. the wet file is better.

## language_identification
b. some language identified failed (misclassification) or some languages mixed usaged. mitigating these issues requires robust language identification, probability of all label or a suitable classifier confidence threshold.

c. the 49th WARC responce is contaminated, is classified as fr(0.2117), but i think it's English. a suitable classifier confidence threshold is 0.6.

## mask_pii
4. some personal identifiable information is hard to filter like address or real name, and this mask will invalid in unformated/raw data, like the format of ip is ipv6, the email use # instand of @, and the phone is just a number not the real phone number or the phone number in other country. it is hard to mitigate this issues, prehaps we can try a model based filter.

5. too many failed case, like 
```
http://www.56.com/n_v162_/c50_/22_/19_/lily_zl_/126612472712hd_/648000_/0_/49549788.swf
masked as
http://www.56.com/n_v162_/c50_/22_/19_/lily_zl_/|||PHONE_NUMBER|||12hd_/648000_/0_/49549788.swf
```


