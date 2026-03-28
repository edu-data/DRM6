/* =========================================================================
   DRM6 Survey - Google Apps Script Backend
   Sheets: Responses, Activities
   - 시간대별 활동 기록 (오전·점심, 오후, 저녁)
   - 정서: 리커트 7점 (즐거운, 행복한, 편안한, 짜증나는, 부정적인, 무기력한, 의미있는, 가치있는, 만족할만한)
   ========================================================================= */

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    var ss = SpreadsheetApp.openById('1p2QRk3zNjpg9VDXBoLsJOTRLV0bW24vsj1P-6X2dTHM');
    var respondentId = Utilities.getUuid();
    var timestamp = new Date().toISOString();

    var allActivities = data.activities || [];
    var counts = data.activityCounts || {};
    var demo = data.demographics || {};

    // 1. Responses Sheet
    var respHeaders = [
      'Timestamp', 'RespondentID', 'PhoneNumber',
      'MorningCount', 'AfternoonCount', 'EveningCount',
      'Gender', 'SchoolLocation', 'SchoolType', 'Grade', 'CareerDecision'
    ];

    var respSheet = getOrCreateSheet(ss, 'Responses', respHeaders);

    respSheet.appendRow([
      timestamp,
      respondentId,
      data.phoneNumber || '',
      counts.morning || 0,
      counts.afternoon || 0,
      counts.evening || 0,
      demo.gender || '',
      demo.schoolLocation || '',
      demo.schoolType || '',
      demo.grade || '',
      demo.careerDecision || ''
    ]);

    // 2. Activities Sheet (통합 - TimeBlock으로 구분)
    var actHeaders = [
      'RespondentID', 'Date', 'DayOfWeek', 'TimeBlock', 'ActivityNum',
      'Activity', 'TimeCategory', 'Companion', 'Location', 'Reason',
      'EmoJoyful', 'EmoHappy', 'EmoComfortable',
      'EmoAnnoyed', 'EmoNegative', 'EmoLethargic',
      'EmoMeaningful', 'EmoValuable', 'EmoSatisfying'
    ];

    var actSheet = getOrCreateSheet(ss, 'Activities', actHeaders);
    var now = new Date();
    var dayNames = ['일요일', '월요일', '화요일', '수요일', '목요일', '금요일', '토요일'];
    var dateStr = Utilities.formatDate(now, Session.getScriptTimeZone(), 'yyyy-MM-dd');
    var dayOfWeek = dayNames[now.getDay()];

    allActivities.forEach(function(a) {
      actSheet.appendRow([
        respondentId,
        dateStr,
        dayOfWeek,
        a.timeBlock || '',
        a.activityNum || '',
        a.activity || '',
        a.time || '',
        a.companion || '',
        a.location || '',
        a.reason || '',
        a.emo_joyful || '',
        a.emo_happy || '',
        a.emo_comfortable || '',
        a.emo_annoyed || '',
        a.emo_negative || '',
        a.emo_lethargic || '',
        a.emo_meaningful || '',
        a.emo_valuable || '',
        a.emo_satisfying || ''
      ]);
    });

    return createJsonResponse({ success: true, respondentId: respondentId });
  } catch (err) {
    return createJsonResponse({ success: false, error: err.toString() });
  }
}

function doGet(e) {
  var ss = SpreadsheetApp.openById('1p2QRk3zNjpg9VDXBoLsJOTRLV0bW24vsj1P-6X2dTHM');
  var result = {};
  ['Responses', 'Activities'].forEach(function(name) {
    var sheet = ss.getSheetByName(name);
    if (sheet) result[name] = sheet.getDataRange().getValues();
  });
  return createJsonResponse(result);
}

function getOrCreateSheet(ss, name, headers) {
  var sheet = ss.getSheetByName(name);
  if (!sheet) {
    sheet = ss.insertSheet(name);
    sheet.appendRow(headers);
    sheet.getRange(1, 1, 1, headers.length).setFontWeight('bold').setBackground('#f3f3f3');
  }
  return sheet;
}

function createJsonResponse(data) {
  return ContentService.createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}
