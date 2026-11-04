import XCTest

/// Uses an isolated fixture supplied through the mobile API, never resets user data.
final class RoutineWatchUITests: XCTestCase {
    let app = XCUIApplication(bundleIdentifier: "app.algoroutine.watchproof")
    override func setUpWithError() throws {
        continueAfterFailure = false
        app.launchArguments = ["-demo-server","-app-language","ko"]
        app.launch()
    }
    func title(_ value: String) -> XCUIElement { app.descendants(matching: .any).matching(identifier: "상세: " + value).firstMatch }
    func point(_ x: CGFloat, _ y: CGFloat) -> XCUICoordinate { app.coordinate(withNormalizedOffset: CGVector(dx:x,dy:y)) }
    func capture(_ name:String) { let a=XCTAttachment(screenshot:app.screenshot());a.name=name;a.lifetime = .keepAlways;add(a) }
    func reserve(_ body:[String:Any]) throws {
        var req=URLRequest(url:URL(string:"http://127.0.0.1:8780/api/execution/reservations")!);req.httpMethod="POST";req.httpBody=try JSONSerialization.data(withJSONObject:body);req.setValue("application/json",forHTTPHeaderField:"Content-Type");req.setValue("local",forHTTPHeaderField:"X-Routine-App")
        let done=expectation(description:"reservation fixture");var code=0
        URLSession.shared.dataTask(with:req){_,response,_ in code=(response as? HTTPURLResponse)?.statusCode ?? 0;done.fulfill()}.resume();wait(for:[done],timeout:12);XCTAssertEqual(code,200)
    }
    func testIdleFutureAndConflictCanRefocus() throws {
        let initial=try workspace();let original=(initial["runs"] as! [[String:Any]])[0];let d=original["definition"] as! [String:Any];let id=UUID().uuidString
        _=try call("/api/execution/command",["id":UUID().uuidString,"kind":"start","occurrenceId":id,"expectedRevision":initial["revision"]!,"definition":d])
        let run=(try workspace()["runs"] as! [[String:Any]]).first{$0["id"] as? String==id}!
        let completion=try call("/api/execution/command",["id":UUID().uuidString,"kind":"completeParent","occurrenceId":id,"expectedRevision":run["revision"]!,"expectedFocusRevision":try workspace()["focusRevision"]!]);XCTAssertEqual((completion["result"] as? [String:Any])?["accepted"] as? Bool,true)
        let before=try workspace()
        XCTAssertTrue(app.staticTexts["다음 작업 없음"].waitForExistence(timeout:15));XCTAssertTrue(app.staticTexts["다음 작업 없음"].isHittable);capture("support-idle")
        app.buttons["함께 진행 1"].tap();XCTAssertTrue(app.buttons[d["title"] as! String].waitForExistence(timeout:5));capture("support-together")
        app.buttons["현재"].tap();XCTAssertTrue(NSDictionary(dictionary:before).isEqual(to:try workspace()))
        let now=Int64(Date().timeIntervalSince1970*1000)
        try reserve(["id":"future-one","definitionId":d["id"]!,"definitionVersion":d["version"]!,"title":d["title"]!,"startMillis":now+3600000,"endMillis":now+7200000])
        XCTAssertTrue(app.staticTexts["예약 예정"].waitForExistence(timeout:8));app.swipeUp();XCTAssertTrue(app.buttons["함께 진행 1"].isHittable);capture("support-future")
        try reserve(["id":"future-two","definitionId":d["id"]!,"definitionVersion":d["version"]!,"title":d["title"]!,"startMillis":now+3600000,"endMillis":now+7200000])
        XCTAssertTrue(app.staticTexts["예약 선택"].waitForExistence(timeout:8));app.swipeUp();app.swipeUp();XCTAssertTrue(app.buttons["함께 진행 1"].isHittable);capture("support-conflict")
        XCTAssertTrue(NSDictionary(dictionary:before).isEqual(to:try workspace()))
        app.buttons["함께 진행 1"].tap();app.buttons[d["title"] as! String].tap();XCTAssertTrue(title("문서 열기").waitForExistence(timeout:8))
        let after=try workspace();XCTAssertEqual(after["focusId"] as? String,original["id"] as? String)
        let runs=after["runs"] as! [[String:Any]];XCTAssertEqual(runs.count,2);XCTAssertTrue(NSDictionary(dictionary:original).isEqual(to:runs.first{$0["id"] as? String==original["id"] as? String}!))
    }
    func testUnavailableIsNotEmpty() throws {
        XCTAssertTrue(app.staticTexts["일정을 확인할 수 없어요"].waitForExistence(timeout:15))
        XCTAssertFalse(app.staticTexts["다음 작업 없음"].exists)
        app.swipeUp();XCTAssertTrue(app.buttons["새로고침"].isHittable);capture("support-unavailable")
    }
    func testEnglishAndKoreanChrome() throws {
        let before=try workspace()
        app.terminate();app.launchArguments=["-demo-server","-app-language","en"];app.launch()
        XCTAssertTrue(app.buttons["Find"].waitForExistence(timeout:15));capture("language-english")
        app.buttons["Find"].tap()
        XCTAssertTrue(app.buttons["Enter a request"].waitForExistence(timeout:10));app.buttons["Enter a request"].tap()
        XCTAssertTrue(app.buttons["Language: English"].waitForExistence(timeout:5));capture("language-picker")
        app.buttons["Language: English"].tap();XCTAssertTrue(app.buttons["언어: 한국어"].waitForExistence(timeout:5))
        app.terminate();app.launchArguments=["-demo-server"];app.launch()
        XCTAssertTrue(app.buttons["찾기"].waitForExistence(timeout:15));capture("language-korean")
        XCTAssertTrue(NSDictionary(dictionary:before).isEqual(to:try workspace()))
    }
    func testColdLaunchReady() throws {
        for index in 0..<3 {
            app.terminate();let started=Date();app.launch()
            XCTAssertTrue(title("문서 열기").waitForExistence(timeout:15))
            print("RoutineStartup cold_launch_to_title_ms=\(Int(Date().timeIntervalSince(started)*1000)) sample=\(index+1)")
        }
        capture("startup-current")
    }
    func testDetailChoiceAndExpiry() throws {
        XCTAssertTrue(app.staticTexts["예약 선택"].waitForExistence(timeout:15));let before=try workspace();capture("gap-choices")
        app.swipeUp();app.buttons["예약: 예약 B"].tap();XCTAssertTrue(app.staticTexts["예약 B"].waitForExistence(timeout:5));capture("gap-preview")
        XCTAssertTrue(NSDictionary(dictionary:before).isEqual(to:try workspace()))
        app.buttons["예약 목록"].tap();app.swipeUp();app.buttons["예약: 예약 B"].tap();app.buttons["시작"].tap()
        XCTAssertTrue(title("선택한 행동").waitForExistence(timeout:10));let started=try workspace();let runs=started["runs"] as! [[String:Any]];XCTAssertEqual(runs.count,1);XCTAssertEqual(started["focusId"] as? String,"reserved-gap-b")
        let d=runs[0]["definition"] as! [String:Any]
        _=try call("/api/commands",["commandId":UUID().uuidString,"kind":"saveDefinition","definitionId":d["id"]!,"expectedVersion":1,"content":["title":"수정된 원본","description":"수정된 설명","steps":[["id":"0","title":"수정된 행동"]]]])
        title("선택한 행동").tap();XCTAssertTrue(app.staticTexts["예약 B"].waitForExistence(timeout:5))
        XCTAssertTrue(app.staticTexts[d["author"] as! String].exists);XCTAssertTrue(app.staticTexts["처음 저장한 설명"].exists);capture("gap-detail")
        app.scrollViews.firstMatch.swipeUp();XCTAssertTrue(app.staticTexts["2. 다음 단계"].isHittable);capture("gap-steps")
        app.buttons["현재"].tap();XCTAssertTrue(title("선택한 행동").waitForExistence(timeout:5));XCTAssertTrue(NSDictionary(dictionary:started).isEqual(to:try workspace()))
        let items=try call("/api/library")["items"] as! [[String:Any]];let short=items.first{$0["title"] as? String=="짧은 예약"}!;let now=Int64(Date().timeIntervalSince1970*1000)
        try reserve(["id":"gap-short","definitionId":short["id"]!,"definitionVersion":1,"title":"짧은 예약","startMillis":now-1000,"endMillis":now+12000])
        _=try call("/api/execution/command",["id":UUID().uuidString,"kind":"start","occurrenceId":"reserved-gap-short","expectedRevision":try workspace()["revision"]!,"definition":["id":short["id"]!,"version":1,"title":"","author":"","steps":[]]])
        XCTAssertTrue(title("잠깐 집중").waitForExistence(timeout:8));capture("gap-timed")
        XCTAssertTrue(app.buttons["시작"].waitForExistence(timeout:20));XCTAssertTrue(title("예약 A").exists);capture("gap-after-expiry")
        let ended=try workspace();let final=ended["runs"] as! [[String:Any]];XCTAssertEqual(final.count,2);let r=final.first{$0["id"] as? String=="reserved-gap-short"}!
        XCTAssertEqual(r["status"] as? String,"elapsed");XCTAssertEqual(r["completed"] as? Int,0);XCTAssertEqual(r["skipped"] as? Int,0);XCTAssertTrue(app.buttons["함께 진행 1"].exists)
    }
    func testCrown() throws {
        XCTAssertTrue(title("문서 열기").waitForExistence(timeout:15))
        let before=try workspace()["revision"] as! Int
        XCUIDevice.shared.rotateDigitalCrown(delta:-0.25,velocity:0.5)
        capture("crown-after")
        XCTAssertTrue(app.staticTexts["탐색 중"].waitForExistence(timeout:5))
        XCTAssertTrue(app.buttons["현재"].exists)
        XCTAssertEqual(try workspace()["revision"] as? Int,before)
        XCUIDevice.shared.rotateDigitalCrown(delta:0.25,velocity:0.5)
        XCTAssertTrue(title("문서 열기").waitForExistence(timeout:5))
        XCTAssertEqual(try workspace()["revision"] as? Int,before)
    }
    func testHoldSlide() throws {
        XCTAssertTrue(title("문서 열기").waitForExistence(timeout:15))
        let before=try workspace()["revision"] as! Int
        point(0.5,0.78).press(forDuration:0.8)
        XCTAssertTrue(title("문서 열기").exists)
        XCTAssertEqual(try workspace()["revision"] as? Int,before)
        point(0.5,0.78).press(forDuration:0.8,thenDragTo:point(0.5,0.60))
        XCTAssertTrue(title("문서 열기").exists)
        XCTAssertEqual(try workspace()["revision"] as? Int,before)
        point(0.5,0.78).press(forDuration:0.8,thenDragTo:point(0.5,0.38))
        capture("hold-slide-after")
        XCTAssertTrue(title("가제 적기").waitForExistence(timeout:10))
    }
    func call(_ path:String,_ body:[String:Any]?=nil) throws -> [String:Any] {
        var req=URLRequest(url:URL(string:"http://127.0.0.1:8780"+path)!)
        if let body=body {req.httpMethod="POST";req.httpBody=try JSONSerialization.data(withJSONObject:body);req.setValue("application/json",forHTTPHeaderField:"Content-Type");req.setValue("local",forHTTPHeaderField:"X-Routine-App")}
        let done=expectation(description:"local integration API");var result:Data?;var failure:Error?;var status=0
        URLSession.shared.dataTask(with:req){data,response,error in result=data;failure=error;status=(response as? HTTPURLResponse)?.statusCode ?? 0;done.fulfill()}.resume()
        wait(for:[done],timeout:12);if let e=failure{throw e};XCTAssertEqual(status,200)
        return try JSONSerialization.jsonObject(with:result!) as! [String:Any]
    }
    func workspace() throws -> [String:Any] {try call("/api/execution/context")["workspace"] as! [String:Any]}
    func testFullFlow() throws {
        // seed_ui_flow.py must have prepared a fresh isolated server with a current reservation.
        XCTAssertTrue(app.buttons["시작"].waitForExistence(timeout:15));app.buttons["시작"].tap()
        XCTAssertTrue(title("문서 열기").waitForExistence(timeout:10))
        let initial=try workspace();let original=initial["focusId"] as! String
        app.buttons["완료"].tap();XCTAssertTrue(title("가제 적기").waitForExistence(timeout:10))
        let library=try call("/api/library")["items"] as! [[String:Any]]
        let other=library.first{$0["title"] as? String == "함께 진행 검증"}!
        let w=try workspace()
        _=try call("/api/execution/command",["id":UUID().uuidString,"kind":"start","occurrenceId":UUID().uuidString,"expectedRevision":w["revision"]!,"definition":["id":other["id"]!,"version":other["version"]!,"title":other["title"]!,"author":"","steps":other["steps"]!]])
        XCTAssertTrue(title("호흡 고르기").waitForExistence(timeout:10))
        app.buttons["함께 진행 1"].tap()
        XCTAssertTrue(app.buttons["통합 검증 루틴"].waitForExistence(timeout:5));app.buttons["통합 검증 루틴"].tap()
        XCTAssertTrue(title("가제 적기").waitForExistence(timeout:10))
        let before=try workspace();XCTAssertEqual(before["focusId"] as? String,original)
        app.terminate();app.launch()
        XCTAssertTrue(title("가제 적기").waitForExistence(timeout:15))
        let after=try workspace();XCTAssertEqual(before["revision"] as? Int,after["revision"] as? Int)
        capture("flow-restored")
        app.buttons["완료"].tap();XCTAssertTrue(title("키워드 적기").waitForExistence(timeout:10))
        app.buttons["완료"].tap();XCTAssertTrue(app.staticTexts["다음 작업 없음"].waitForExistence(timeout:10))
        let end=try workspace();let runs=end["runs"] as! [[String:Any]];let r=runs.first{$0["id"] as? String == original}!
        XCTAssertEqual(r["completed"] as? Int,3);capture("flow-finished")
    }

    /// Accepts the actual mobile-started recommendation without assuming its title or step count.
    func testLiveRecommendationCompleteAndReturn() throws {
        let initial=try workspace(), runs=initial["runs"] as! [[String:Any]]
        let focused=runs.first{$0["id"] as? String==initial["focusId"] as? String}!
        let original=runs.first{$0["id"] as? String=="voice-original"}!
        XCTAssertNotEqual(focused["id"] as? String,"voice-original")
        let definition=focused["definition"] as! [String:Any]
        let steps=definition["steps"] as! [[String:Any]]
        XCTAssertFalse(steps.isEmpty)
        XCTAssertTrue(title(steps[0]["title"] as! String).waitForExistence(timeout:20))
        capture("live-recommendation-start")
        app.buttons["함께 진행 1"].tap()
        XCTAssertTrue(app.buttons["기존 진행 루틴"].waitForExistence(timeout:8));app.buttons["기존 진행 루틴"].tap()
        XCTAssertTrue(title("기존 행동").waitForExistence(timeout:8));capture("live-return-original")
        app.buttons["함께 진행 1"].tap()
        let routineTitle=definition["title"] as! String
        XCTAssertTrue(app.buttons[routineTitle].waitForExistence(timeout:8));app.buttons[routineTitle].tap()
        for (index,step) in steps.enumerated() {
            XCTAssertTrue(title(step["title"] as! String).waitForExistence(timeout:10))
            capture("live-step-\(index)");app.buttons["완료"].tap()
        }
        XCTAssertTrue(app.staticTexts["다음 예약"].waitForExistence(timeout:12));capture("live-next-reservation")
        let end=try workspace(),endRuns=end["runs"] as! [[String:Any]]
        XCTAssertTrue(NSDictionary(dictionary:original).isEqual(to:endRuns.first{$0["id"] as? String=="voice-original"}!))
        let done=endRuns.first{$0["id"] as? String==focused["id"] as? String}!
        XCTAssertEqual(done["status"] as? String,"completed");XCTAssertEqual(done["completed"] as? Int,steps.count)
        XCTAssertFalse(endRuns.contains{$0["id"] as? String=="reserved-voice-next"})
    }

    func testMobileVoiceStartCompleteAndReturn() throws {
        XCTAssertTrue(title("모바일 첫 행동").waitForExistence(timeout:15))
        let initial=try workspace()
        let old=(initial["runs"] as! [[String:Any]]).first{$0["id"] as? String=="voice-original"}!
        capture("voice-mobile-start")
        app.buttons["함께 진행 1"].tap()
        XCTAssertTrue(app.buttons["기존 진행 루틴"].waitForExistence(timeout:5));app.buttons["기존 진행 루틴"].tap()
        XCTAssertTrue(title("기존 행동").waitForExistence(timeout:8));capture("voice-return-original")
        app.buttons["함께 진행 1"].tap()
        XCTAssertTrue(app.buttons["음성으로 시작한 루틴"].waitForExistence(timeout:5));app.buttons["음성으로 시작한 루틴"].tap()
        XCTAssertTrue(title("모바일 첫 행동").waitForExistence(timeout:8))
        app.buttons["완료"].tap();XCTAssertTrue(title("모바일 다음 행동").waitForExistence(timeout:8));capture("voice-next-step")
        app.buttons["완료"].tap();XCTAssertTrue(app.staticTexts["다음 예약"].waitForExistence(timeout:10));capture("voice-next-reservation")
        let end=try workspace(),runs=end["runs"] as! [[String:Any]]
        XCTAssertTrue(NSDictionary(dictionary:old).isEqual(to:runs.first{$0["id"] as? String=="voice-original"}!))
        let generated=runs.first{$0["id"] as? String=="voice-generated"}!
        XCTAssertEqual(generated["status"] as? String,"completed")
        XCTAssertEqual(generated["completed"] as? Int,2)
        XCTAssertFalse(runs.contains{$0["id"] as? String=="reserved-voice-next"})
    }

    func testFindStartReturn() throws {
        XCTAssertTrue(app.buttons["시작"].waitForExistence(timeout:15));app.buttons["시작"].tap()
        XCTAssertTrue(title("문서 열기").waitForExistence(timeout:10));app.buttons["완료"].tap()
        XCTAssertTrue(title("가제 적기").waitForExistence(timeout:10))
        let before=try workspace(),original=before["focusId"] as! String
        let old=(before["runs"] as! [[String:Any]]).first{$0["id"] as? String==original}!
        app.buttons["찾기"].tap()
        let other=app.buttons["루틴: 함께 진행 검증"]
        XCTAssertTrue(other.waitForExistence(timeout:10));other.tap()
        XCTAssertTrue(app.staticTexts["1. 호흡 고르기"].waitForExistence(timeout:5))
        for _ in 0..<3 {if app.buttons["시작"].isHittable{break};app.swipeUp()}
        XCTAssertTrue(app.staticTexts["2. 한 줄 정리"].exists)
        XCTAssertEqual(before["revision"] as? Int,try workspace()["revision"] as? Int)
        capture("find-detail");app.buttons["시작"].tap()
        XCTAssertTrue(title("호흡 고르기").waitForExistence(timeout:10))
        let started=try workspace();XCTAssertEqual((started["runs"] as! [[String:Any]]).count,(before["runs"] as! [[String:Any]]).count+1)
        XCTAssertTrue(NSDictionary(dictionary:old).isEqual(to:(started["runs"] as! [[String:Any]]).first{$0["id"] as? String==original}!))
        capture("find-started");app.buttons["함께 진행 1"].tap()
        XCTAssertTrue(app.buttons["통합 검증 루틴"].waitForExistence(timeout:5));app.buttons["통합 검증 루틴"].tap()
        XCTAssertTrue(title("가제 적기").waitForExistence(timeout:10))
        let returned=try workspace();XCTAssertEqual(returned["focusId"] as? String,original)
        XCTAssertTrue(NSDictionary(dictionary:old).isEqual(to:(returned["runs"] as! [[String:Any]]).first{$0["id"] as? String==original}!))
        capture("find-returned");app.buttons["찾기"].tap()
        XCTAssertTrue(app.buttons["현재"].waitForExistence(timeout:5));app.buttons["현재"].tap()
        XCTAssertTrue(title("가제 적기").waitForExistence(timeout:5));XCTAssertEqual(returned["revision"] as? Int,try workspace()["revision"] as? Int)
    }

    func control(_ path:String) throws {
        let ready=expectation(description:"isolated proxy control")
        var failure:Error?;var status=0
        URLSession.shared.dataTask(with:URL(string:"http://127.0.0.1:8791/test/"+path)!){_,response,error in failure=error;status=(response as? HTTPURLResponse)?.statusCode ?? 0;ready.fulfill()}.resume()
        wait(for:[ready],timeout:8);if let error=failure{throw error};XCTAssertEqual(status,200)
    }
    func testConnectionKeepsInput() throws {
        XCTAssertTrue(title("문서 열기").waitForExistence(timeout:15));let before=try workspace()["revision"] as! Int
        app.buttons["찾기"].tap();XCTAssertTrue(app.buttons["검색 입력"].waitForExistence(timeout:10));app.buttons["검색 입력"].tap()
        let field=app.textFields["검색 내용"];XCTAssertTrue(field.waitForExistence(timeout:5));field.tap();app.typeText("keep")
        if app.buttons["Done"].exists{app.buttons["Done"].tap()}else if app.buttons["완료"].exists{app.buttons["완료"].tap()}else{app.typeText("\n")}
        XCTAssertTrue((field.value as? String)?.contains("keep") == true)
        try control("offline");defer{try? control("online")}
        XCTAssertTrue(app.staticTexts["연결 후 결과 확인"].waitForExistence(timeout:10));capture("connection-error")
        try control("online");app.buttons["결과 확인"].tap()
        XCTAssertTrue(field.waitForExistence(timeout:10));XCTAssertTrue((field.value as? String)?.contains("keep") == true)
        XCTAssertEqual(try workspace()["revision"] as? Int,before);capture("connection-restored")
    }
    func testDeckNavigation() throws {
        XCTAssertTrue(app.buttons["시작"].waitForExistence(timeout:15))
        let before=try workspace()["revision"] as! Int
        app.buttons["찾기"].tap()
        XCTAssertTrue(app.buttons["루틴: 함께 진행 검증"].waitForExistence(timeout:10));capture("deck-first")
        app.swipeUp();XCTAssertTrue(app.buttons["루틴: 통합 검증 루틴"].waitForExistence(timeout:5));capture("deck-second")
        XCUIDevice.shared.rotateDigitalCrown(delta:0.25,velocity:0.5)
        XCTAssertTrue(app.buttons["루틴: 함께 진행 검증"].waitForExistence(timeout:5))
        XCTAssertEqual(try workspace()["revision"] as? Int,before)
        app.buttons["현재"].tap();XCTAssertTrue(app.buttons["시작"].waitForExistence(timeout:5))
    }
    func testSearchInputAndStart() throws {
        XCTAssertTrue(app.buttons["시작"].waitForExistence(timeout:15));app.buttons["시작"].tap()
        XCTAssertTrue(title("문서 열기").waitForExistence(timeout:10));app.buttons["완료"].tap()
        XCTAssertTrue(title("가제 적기").waitForExistence(timeout:10))
        let before=try workspace(),original=before["focusId"] as! String
        app.buttons["찾기"].tap()
        XCTAssertTrue(app.buttons["검색 입력"].waitForExistence(timeout:10));app.buttons["검색 입력"].tap()
        let field=app.textFields["검색 내용"]
        XCTAssertTrue(field.waitForExistence(timeout:10));field.tap()
        capture("search-system-input")
        app.typeText("breath")
        if app.buttons["Done"].exists{app.buttons["Done"].tap()}
        else if app.buttons["완료"].exists{app.buttons["완료"].tap()}
        else{app.typeText("\n")}
        XCTAssertTrue((field.value as? String)?.contains("breath") == true)
        XCTAssertEqual(try workspace()["revision"] as? Int,before["revision"] as? Int)
        for _ in 0..<4 {if app.buttons["찾기"].isHittable{break};app.swipeUp()}
        app.buttons["찾기"].tap()
        let result=app.buttons["루틴: 함께 진행 검증"]
        XCTAssertTrue(result.waitForExistence(timeout:10))
        XCTAssertFalse(app.buttons["루틴: 통합 검증 루틴"].exists)
        for _ in 0..<6 {if result.isHittable{break};app.swipeUp()}
        capture("search-results");result.tap()
        for _ in 0..<5 {if app.buttons["시작"].isHittable{break};app.swipeUp()}
        app.buttons["시작"].tap();XCTAssertTrue(title("호흡 고르기").waitForExistence(timeout:10))
        app.buttons["함께 진행 1"].tap();XCTAssertTrue(app.buttons["통합 검증 루틴"].waitForExistence(timeout:5));app.buttons["통합 검증 루틴"].tap()
        XCTAssertTrue(title("가제 적기").waitForExistence(timeout:10));XCTAssertEqual(try workspace()["focusId"] as? String,original);capture("search-returned")
    }

}

/// Disposable server profile: never sends commands to the user's 8791 workspace.
final class RemainingWatchFlowTests: XCTestCase {
 let app=XCUIApplication(bundleIdentifier:"app.algoroutine.watchproof")
 override func setUpWithError() throws {continueAfterFailure=false}
 override func tearDownWithError() throws {_ = try? api("/__mode",["mode":"normal"]);app.terminate()}
 func api(_ path:String,_ body:[String:Any]?=nil) throws->[String:Any]{
  var req=URLRequest(url:URL(string:"http://127.0.0.1:8793"+path)!);req.timeoutInterval=12
  if let b=body {req.httpMethod="POST";req.httpBody=try JSONSerialization.data(withJSONObject:b);req.setValue("application/json",forHTTPHeaderField:"Content-Type")}
  let e=expectation(description:path);var data:Data?;var error:Error?;var status=0
  URLSession.shared.dataTask(with:req){d,r,f in data=d;error=f;status=(r as? HTTPURLResponse)?.statusCode ?? 0;e.fulfill()}.resume()
  wait(for:[e],timeout:15);if let f=error{throw f};XCTAssertEqual(status,200);return try JSONSerialization.jsonObject(with:data!) as! [String:Any]
 }
 func workspace()throws->[String:Any]{try api("/context")["workspace"] as! [String:Any]}
 func launch(_ scenario:String,_ language:String="en")throws{app.terminate();_ = try api("/__reset",["scenario":scenario]);app.launchArguments=["-demo-server","-verification-port","8793","-app-language",language];app.launch()}
 func title(_ value:String)->XCUIElement{app.descendants(matching:.any).matching(identifier:"Details: "+value).firstMatch}
 func capture(_ name:String){let a=XCTAttachment(screenshot:app.screenshot());a.name="remaining-"+name;a.lifetime = .keepAlways;add(a)}
 func point(_ x:CGFloat,_ y:CGFloat)->XCUICoordinate{app.coordinate(withNormalizedOffset:CGVector(dx:x,dy:y))}
 func equal(_ a:[String:Any],_ b:[String:Any]){XCTAssertTrue(NSDictionary(dictionary:a).isEqual(to:b))}
 func runs(_ w:[String:Any])->NSArray{NSArray(array:w["runs"] as! [[String:Any]])}
 func testConcurrentPreviewFocusReturn()throws{
  try launch("concurrent");XCTAssertTrue(title("Write heading").waitForExistence(timeout:15));let before=try workspace();capture("concurrent-current")
  app.buttons["Other tasks: 1"].tap();XCTAssertTrue(app.buttons["Reset focus"].waitForExistence(timeout:5));capture("concurrent-list");app.buttons["Reset focus"].tap()
  XCTAssertTrue(app.buttons["Focus here"].waitForExistence(timeout:5));capture("concurrent-preview");for _ in 0..<4 {if app.staticTexts["2 · Choose next action"].isHittable{break};app.scrollViews.firstMatch.swipeUp()};XCTAssertTrue(app.staticTexts["2 · Choose next action"].isHittable);capture("concurrent-preview-scrolled");equal(before,try workspace())
  app.buttons["Focus here"].tap();XCTAssertTrue(title("Take one breath").waitForExistence(timeout:10));capture("concurrent-other")
  XCTAssertEqual(try workspace()["focusId"] as? String,"other");XCTAssertEqual(runs(before),runs(try workspace()))
  app.buttons["Other tasks: 1"].tap();app.buttons["Report draft"].tap();capture("concurrent-original-preview");app.buttons["Focus here"].tap()
  XCTAssertTrue(title("Write heading").waitForExistence(timeout:10));capture("concurrent-return");let after=try workspace()
  XCTAssertEqual(after["focusId"] as? String,"original");XCTAssertEqual(runs(before),runs(after));XCTAssertEqual(after["revision"] as! Int,(before["revision"] as! Int)+2)
  app.terminate();app.launch();XCTAssertTrue(title("Write heading").waitForExistence(timeout:15));equal(after,try workspace());capture("concurrent-relaunched")
 }
 func testGestureCrownDetailsAndParentCompletion()throws{
  try launch("gesture");XCTAssertTrue(title("Open document").waitForExistence(timeout:15));let before=try workspace()
  XCUIDevice.shared.rotateDigitalCrown(delta:-0.25,velocity:0.5);XCTAssertTrue(app.staticTexts["Exploring"].waitForExistence(timeout:5));capture("crown-explore");equal(before,try workspace());point(0.5,0.78).tap()
  title("Open document").tap();XCTAssertTrue(app.buttons["Current"].waitForExistence(timeout:5));capture("step-detail");app.buttons["Back"].tap();app.scrollViews.firstMatch.swipeUp();capture("full-detail");app.buttons["Current"].tap();equal(before,try workspace())
  point(0.5,0.78).press(forDuration:0.8);XCTAssertTrue(title("Open document").exists);equal(before,try workspace())
  point(0.5,0.78).press(forDuration:0.8,thenDragTo:point(0.5,0.38));XCTAssertTrue(title("Write heading").waitForExistence(timeout:10));capture("deferred")
  point(0.5,0.78).tap();XCTAssertTrue(title("Open document").waitForExistence(timeout:10))
  point(0.5,0.5).tap();XCTAssertTrue(app.buttons["Skip"].waitForExistence(timeout:5));capture("options");point(0.78,0.38).tap();XCTAssertTrue(title("List key points").waitForExistence(timeout:10))
  point(0.2,0.5).press(forDuration:0.05,thenDragTo:point(0.8,0.5));XCTAssertTrue(title("Report draft").waitForExistence(timeout:5));capture("parent");point(0.5,0.78).tap()
  XCTAssertTrue(app.staticTexts["No upcoming tasks"].waitForExistence(timeout:10));let r=(try workspace()["runs"] as! [[String:Any]])[0];XCTAssertEqual(r["status"] as? String,"completed");XCTAssertEqual(r["evidence"] as? String,"direct_parent");XCTAssertEqual(r["completed"] as? Int,1);XCTAssertEqual(r["skipped"] as? Int,1);capture("parent-completed")
 }
 func testReservationAndExpiry()throws{
  try launch("conflict");XCTAssertTrue(app.staticTexts["Choose a schedule"].waitForExistence(timeout:15));let before=try workspace();capture("reservation-conflict")
  app.scrollViews.firstMatch.swipeUp();app.buttons["Schedule: Reset focus"].tap();XCTAssertTrue(app.buttons["Start"].waitForExistence(timeout:5));equal(before,try workspace());capture("reservation-preview");app.buttons["Start"].tap();XCTAssertTrue(title("Take one breath").waitForExistence(timeout:10));XCTAssertEqual(try workspace()["focusId"] as? String,"reserved-choice-b")
  try launch("timed");XCTAssertTrue(title("Take one breath").waitForExistence(timeout:15));point(0.2,0.5).press(forDuration:0.05,thenDragTo:point(0.8,0.5));capture("timed-running")
  XCTAssertTrue(title("Next reservation").waitForExistence(timeout:60));XCTAssertTrue(app.buttons["Start"].exists);capture("timed-expired-next")
  let rs=try workspace()["runs"] as! [[String:Any]];XCTAssertEqual(rs.count,1);XCTAssertEqual(rs[0]["status"] as? String,"elapsed");XCTAssertEqual(rs[0]["completed"] as? Int,0);XCTAssertEqual(rs[0]["skipped"] as? Int,0)
 }
 func testConnectionRecoveryAndLostResponse()throws{
  try launch("active");XCTAssertTrue(title("Open document").waitForExistence(timeout:15));let before=try workspace();_ = try api("/__mode",["mode":"read_error"])
  XCTAssertTrue(app.buttons["Check result"].waitForExistence(timeout:15));capture("connection-error");_ = try api("/__mode",["mode":"normal"])
  let cleared=XCTNSPredicateExpectation(predicate:NSPredicate(format:"exists == false"),object:app.buttons["Check result"]);XCTAssertEqual(XCTWaiter.wait(for:[cleared],timeout:15),.completed);XCTAssertTrue(app.buttons["Done"].isHittable);capture("connection-recovered");equal(before,try workspace())
  _ = try api("/__mode",["mode":"drop_command_once"]);point(0.5,0.78).tap();XCTAssertTrue(app.buttons["Check result"].waitForExistence(timeout:10));capture("lost-response");app.buttons["Check result"].tap()
  XCTAssertTrue(title("Write heading").waitForExistence(timeout:15));XCTAssertEqual(try workspace()["revision"] as! Int,(before["revision"] as! Int)+1);capture("lost-response-replayed")
 }
 func testEmptyFutureLongTextAndSearchRecovery()throws{
  try launch("empty");XCTAssertTrue(app.staticTexts["No upcoming tasks"].waitForExistence(timeout:15));capture("empty");XCTAssertEqual((try workspace()["runs"] as! [[String:Any]]).count,0)
  try launch("future");XCTAssertTrue(app.staticTexts["Scheduled"].waitForExistence(timeout:15));XCTAssertFalse(app.buttons["Start"].exists);capture("future")
  try launch("long-ko","ko");let t="보고서 초안을 시작하기 위해 새 문서를 열고 첫 문장을 준비하기";let target=app.descendants(matching:.any).matching(identifier:"상세: "+t).firstMatch
  XCTAssertTrue(target.waitForExistence(timeout:15));capture("long-korean-current");target.tap();capture("long-korean-detail");app.scrollViews.firstMatch.swipeUp();capture("long-korean-scrolled");app.buttons["현재"].tap()
  _ = try api("/__mode",["mode":"search_error"]);app.buttons["찾기"].tap();XCTAssertTrue(app.staticTexts["연결을 확인해 주세요"].waitForExistence(timeout:10));capture("search-error");_ = try api("/__mode",["mode":"normal"]);app.buttons["다시"].tap();XCTAssertTrue(app.buttons["시작"].waitForExistence(timeout:10));capture("search-recovered")
 }
}

/// "My routine" day level on a disposable rest_demo fixture (execution 8793, mobile 8794), clock 17:02 after the rest plan.
/// Set DAY_SHOTS to a directory to save screenshots. Browsing must not change runs or reservations.
final class DayLevelTests: XCTestCase {
 let app=XCUIApplication(bundleIdentifier:"app.algoroutine.watchproof")
 override func setUpWithError() throws {continueAfterFailure=false}
 func get(_ url:String) throws->Data {
  let e=expectation(description:url);var data:Data?;URLSession.shared.dataTask(with:URL(string:url)!){d,_,_ in data=d;e.fulfill()}.resume();wait(for:[e],timeout:15);return try XCTUnwrap(data)
 }
 func state() throws->Data {var out=try get("http://127.0.0.1:8793/context");let w=try JSONSerialization.jsonObject(with:out) as! [String:Any];out=try JSONSerialization.data(withJSONObject:[w["workspace"]!,try JSONSerialization.jsonObject(with:get("http://127.0.0.1:8794/api/execution/reservations"))],options:.sortedKeys);return out}
 func el(_ label:String)->XCUIElement{app.descendants(matching:.any).matching(NSPredicate(format:"label == %@",label)).firstMatch}
 func shot(_ name:String){sleep(1);let dir=ProcessInfo.processInfo.environment["DAY_SHOTS"] ?? "/tmp";try? app.screenshot().pngRepresentation.write(to:URL(fileURLWithPath:dir).appendingPathComponent(name+".png"))}
 func testStepToDayBrowseAndBack() throws {
  app.terminate();app.launchArguments=["-demo-server","-verification-port","8793","-app-language","en"];app.launch()
  XCTAssertTrue(el("Details: Write a working heading").waitForExistence(timeout:20));shot("watch-step")
  let before=try state()
  el("Parent: Start a report").tap()
  XCTAssertTrue(el("Details: Start a report").waitForExistence(timeout:5));XCTAssertTrue(el("My routine").exists);shot("watch-day")
  for _ in 0..<3 {app.swipeUp();usleep(400_000)}
  XCTAssertTrue(el("Details: Team sync").waitForExistence(timeout:5));XCTAssertTrue(el("Current").exists);shot("watch-browse")
  XCTAssertEqual(try state(),before,"browsing changed state")
  el("Current").tap();XCTAssertTrue(el("Details: Start a report").waitForExistence(timeout:5))
  el("Details: Start a report").tap();XCTAssertTrue(el("Details: Write a working heading").waitForExistence(timeout:5))
  XCTAssertEqual(try state(),before)
 }
}
