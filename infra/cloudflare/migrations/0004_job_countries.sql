-- Multi-country job filtering metadata.

ALTER TABLE jobs ADD COLUMN countries TEXT DEFAULT '';

UPDATE jobs
SET countries =
  CASE
    WHEN lower(location) LIKE '%germany%'
      OR lower(location) LIKE '%deutschland%'
      OR lower(location) LIKE '%multiple de cities%'
      OR lower(location) LIKE '%multiple germany cities%'
      OR lower(location) LIKE '%remote germany%'
      OR lower(location) LIKE '%nationwide germany%'
      OR lower(location) LIKE '%berlin%'
      OR lower(location) LIKE '%hamburg%'
      OR lower(location) LIKE '%munich%'
      OR lower(location) LIKE '%münchen%'
      OR lower(location) LIKE '%metropolregion münchen%'
      OR lower(location) LIKE '%frankfurt%'
      OR lower(location) LIKE '%stuttgart%'
      OR lower(location) LIKE '%leipzig%'
      OR lower(location) LIKE '%hannover%'
      OR lower(location) LIKE '%karlsruhe%'
      OR lower(location) LIKE '%bremen%'
      OR lower(location) LIKE '%düsseldorf%'
      OR lower(location) LIKE '%duesseldorf%'
      OR lower(location) LIKE '%cologne%'
      OR lower(location) LIKE '%köln%'
      OR lower(location) LIKE '%dortmund%'
      OR lower(location) LIKE '%mainz%'
      OR lower(location) LIKE '%nuremberg%'
      OR lower(location) LIKE '%ulm%'
      OR lower(location) LIKE '%aachen%'
      OR lower(location) LIKE '%darmstadt%'
      OR lower(location) LIKE '%dresden%'
      OR lower(location) LIKE '%duisburg%'
      OR lower(location) LIKE '%erlangen%'
      OR lower(location) LIKE '%eschborn%'
      OR lower(location) LIKE '%freiburg im breisgau%'
      OR lower(location) LIKE '%garching%'
      OR lower(location) LIKE '%göttingen%'
      OR lower(location) LIKE '%heilbronn%'
      OR lower(location) LIKE '%ingolstadt%'
      OR lower(location) LIKE '%kaiserslautern%'
      OR lower(location) LIKE '%kiel%'
      OR lower(location) LIKE '%mannheim%'
      OR lower(location) LIKE '%offenbach%'
      OR lower(location) LIKE '%regensburg%'
      OR lower(location) LIKE '%wiesbaden%'
      OR lower(location) LIKE '%bavaria%'
      OR lower(location) LIKE '%hesse%'
      OR lower(location) LIKE '%saxony%'
      OR lower(location) LIKE '%north rhine-westphalia%'
      OR lower(location) LIKE '%baden-württemberg%'
      OR lower(location) LIKE '%rhineland-palatinate%'
      OR lower(location) LIKE '%schleswig-holstein%'
    THEN '|Germany|' ELSE '' END ||
  CASE
    WHEN lower(location) LIKE '%switzerland%'
      OR lower(location) LIKE '%schweiz%'
      OR lower(location) LIKE '%zurich%'
      OR lower(location) LIKE '%zürich%'
      OR lower(location) LIKE '%basel%'
      OR lower(location) LIKE '%bern%'
      OR lower(location) LIKE '%berne%'
      OR lower(location) LIKE '%baar%'
      OR lower(location) LIKE '%geneva%'
      OR lower(location) LIKE '%genf%'
      OR lower(location) LIKE '%emmen%'
      OR lower(location) LIKE '%lausanne%'
      OR lower(location) LIKE '%fribourg%'
      OR lower(location) LIKE '%gerlafingen%'
      OR lower(location) LIKE '%ittigen%'
      OR lower(location) LIKE '%lucerne%'
      OR lower(location) LIKE '%luzern%'
      OR lower(location) LIKE '%meilen%'
      OR lower(location) LIKE '%mendrisio%'
      OR lower(location) LIKE '%sierre%'
      OR lower(location) LIKE '%solothurn%'
      OR lower(location) LIKE '%st gallen%'
      OR lower(location) LIKE '%zug%'
      OR lower(location) LIKE '%vaud%'
      OR lower(location) LIKE '%waadt%'
      OR lower(location) LIKE '%ticino%'
    THEN '|Switzerland|' ELSE '' END ||
  CASE
    WHEN lower(location) LIKE '%austria%'
      OR lower(location) LIKE '%österreich%'
      OR lower(location) LIKE '%oesterreich%'
      OR lower(location) LIKE '%vienna%'
      OR lower(location) LIKE '%wien%'
    THEN '|Austria|' ELSE '' END ||
  CASE
    WHEN lower(location) LIKE '%united states%'
      OR lower(location) LIKE '%usa%'
      OR lower(location) LIKE '%remote, us%'
      OR lower(location) LIKE '%san francisco%'
      OR lower(location) LIKE '%new york%'
      OR lower(location) LIKE '%austin%'
      OR lower(location) LIKE '%santa clara%'
      OR lower(location) LIKE '%seattle%'
      OR lower(location) LIKE '%cambridge, ma%'
      OR lower(location) LIKE '%boulder, co%'
      OR lower(location) LIKE '%charlotte, nc%'
      OR lower(location) LIKE '%mountain view%'
      OR lower(location) LIKE '%oakland%'
      OR lower(location) LIKE '%redmond%'
      OR lower(location) LIKE '%san jose%'
      OR lower(location) LIKE '%san mateo%'
      OR lower(location) LIKE '%sunnyvale%'
      OR lower(location) LIKE '%, ca%'
      OR lower(location) LIKE '%, ny%'
      OR lower(location) LIKE '%, tx%'
      OR lower(location) LIKE '%, wa%'
      OR lower(location) LIKE '%, ma%'
      OR lower(location) LIKE '%, co%'
      OR lower(location) LIKE '%, nc%'
    THEN '|United States|' ELSE '' END ||
  CASE
    WHEN lower(location) LIKE '%spain%'
      OR lower(location) LIKE '%barcelona%'
      OR lower(location) LIKE '%madrid%'
      OR lower(location) LIKE '%granada%'
    THEN '|Spain|' ELSE '' END ||
  CASE
    WHEN lower(location) LIKE '%united kingdom%'
      OR lower(location) LIKE '%london%'
      OR lower(location) LIKE '%/uk%'
      OR lower(location) LIKE '% uk %'
    THEN '|United Kingdom|' ELSE '' END ||
  CASE
    WHEN lower(location) LIKE '%ireland%'
      OR lower(location) LIKE '%dublin%'
    THEN '|Ireland|' ELSE '' END ||
  CASE
    WHEN lower(location) LIKE '%romania%'
      OR lower(location) LIKE '%iasi%'
    THEN '|Romania|' ELSE '' END ||
  CASE WHEN lower(location) LIKE '%italy%' THEN '|Italy|' ELSE '' END ||
  CASE WHEN lower(location) LIKE '%portugal%' THEN '|Portugal|' ELSE '' END ||
  CASE
    WHEN lower(location) LIKE '%netherlands%'
      OR lower(location) LIKE '%amsterdam%'
    THEN '|Netherlands|' ELSE '' END ||
  CASE
    WHEN lower(location) LIKE '%france%'
      OR lower(location) LIKE '%paris%'
    THEN '|France|' ELSE '' END ||
  CASE
    WHEN lower(location) LIKE '%thailand%'
      OR lower(location) LIKE '%bangkok%'
    THEN '|Thailand|' ELSE '' END ||
  CASE
    WHEN lower(location) LIKE '%japan%'
      OR lower(location) LIKE '%tokyo%'
      OR lower(location) LIKE '%yokohama%'
    THEN '|Japan|' ELSE '' END ||
  CASE
    WHEN lower(location) LIKE '%hungary%'
      OR lower(location) LIKE '%budapest%'
    THEN '|Hungary|' ELSE '' END ||
  CASE
    WHEN lower(location) LIKE '%greece%'
      OR lower(location) LIKE '%athens%'
    THEN '|Greece|' ELSE '' END
WHERE COALESCE(TRIM(location), '') != '';

CREATE INDEX IF NOT EXISTS idx_jobs_countries ON jobs(user_id, countries);
