import SwiftUI
import RoutineCore
import OSLog
import WatchKit

@main
struct RoutineWatchApp: App {
    @AppStorage("app.language") private var language="en"
    init(){let args=ProcessInfo.processInfo.arguments;if let i=args.firstIndex(of:"-app-language"),i+1<args.count{UserDefaults.standard.set(args[i+1],forKey:"app.language")}}
    var body: some Scene { WindowGroup { Group { if DeviceConnection.enabled || ProcessInfo.processInfo.arguments.contains("-demo-server") { RemoteTaskView() } else { CurrentTaskView() } }.environment(\.locale,Locale(identifier:language)) } }
}

final class LocalExecutionStorage: NSObject, ExecutionStorage {
    private var url: URL {
        FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("execution-v1.json")
    }
    func read() -> StorageRead {
        do {
            let data = try Data(contentsOf: url)
            guard let text = String(data: data, encoding: .utf8) else { return StorageRead(content: nil, error: true) }
            return StorageRead(content: text, error: false)
        } catch let error as CocoaError where error.code == .fileReadNoSuchFile {
            return StorageRead(content: nil, error: false)
        } catch { return StorageRead(content: nil, error: true) }
    }
    func write(content: String) -> Bool {
        do {
            try FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
            try Data(content.utf8).write(to: url, options: .atomic)
            return true
        } catch { return false }
    }
}

// One serial owner performs both disk I/O and domain mutations off the main thread.
final class ExecutionWorker {
    private let queue = DispatchQueue(label: "routine.execution")
    private var session: PersistentExecution?
    func perform(target: ExecutionView?, reply: @escaping (ExecutionView?, String?) -> Void) {
        queue.async {
            if let target = target, let stepId = target.currentStepId {
                _ = self.session?.complete(commandId: UUID().uuidString,
                    targetStepId: stepId, expectedRevision: target.revision)
            } else {
                self.session = PersistentFactory().openDemo(storage: LocalExecutionStorage())
            }
            let view = self.session?.view(), error = self.session?.error
            let title = view?.currentTitle ?? "unavailable", count = view?.completedCount ?? -1
            Logger(subsystem: "app.algoroutine.watchproof", category: "RoutinePersistence")
                .notice("current=\(title, privacy: .public) completed=\(count) error=\(error ?? "none", privacy: .public)")
            DispatchQueue.main.async { reply(view, error) }
        }
    }
}

@MainActor
final class ExecutionStore: ObservableObject {
    private let worker = ExecutionWorker()
    @Published private(set) var snapshot: ExecutionView?
    @Published private(set) var error: String?
    @Published private(set) var busy = false
    init() { load() }
    func load() { run(target: nil) }
    func complete(target: ExecutionView) { run(target: target) }
    private func run(target: ExecutionView?) {
        guard !busy else { return }
        busy = true
        worker.perform(target: target) { [weak self] view, error in
            self?.snapshot = view; self?.error = error; self?.busy = false
        }
    }
}

struct CurrentTaskView: View {
 @StateObject private var store=ExecutionStore()
 var body:some View {
  if let error=store.error {VStack{Text(error);Button(L("다시 확인")){store.load()}}}
  else if let v=store.snapshot,let current=v.currentStepId {
   let items=[("open",L("문서 열기")),("title",L("가제 한 줄 적기")),("keywords",L("키워드 세 개 적기"))].enumerated().map{i,item in OrbitNode(id:item.0,title:item.1,status:i<Int(v.completedCount) ? "completed":"pending")}
   OrbitFace(parent:v.parentTitle,nodes:items,currentId:current,token:"local:\(v.revision)",busy:store.busy,optionsEnabled:false,action:{kind in if kind=="complete"{store.complete(target:v)}})
  }else if store.snapshot != nil {Text(L("다음 작업 없음"))}
  else{ProgressView()}
 }
}

// Simulator integration profile. Production authentication and device transport are separate work.
private struct LibraryStep:Decodable {let id:String;let title:String;let description:String?}
private struct LibraryAuthor:Decodable {let name:String}
private struct LibraryRoutine:Decodable,Identifiable {let id:String;let version:Int;let title:String;let description:String;let author:LibraryAuthor;let source:String;let steps:[LibraryStep];let reason:String?}
private struct LibraryReply:Decodable {let items:[LibraryRoutine]}

private struct RemoteStep: Decodable { let id:String; let title:String; let status:String }
private struct RemoteDefinition: Decodable { let id:String; let version:Int; let title:String; let author:String; let description:String?; let windowStartMillis:Double?; let windowEndMillis:Double? }
private struct RemoteRun: Decodable, Identifiable { let id:String; let definition:RemoteDefinition; let revision:Int; let status:String; let currentUnitId:String?; let steps:[RemoteStep];let order:[String]? }
private struct RemoteWorkspace: Decodable { let revision:Int; let focusRevision:Int; let focusId:String?; let runs:[RemoteRun] }
private struct RemoteReservation:Decodable,Identifiable { let id:String; let definitionId:String; let definitionVersion:Int; let title:String; let startMillis:Double; let endMillis:Double; let occurrenceId:String }
private struct RemoteSelection:Decodable { let state:String; let candidates:[RemoteReservation] }
/// One "My routine" (whole day) item from the execution server's core DayOrbit ordering.
private struct RemoteDayItem:Decodable,Identifiable { let kind:String; let id:String; let title:String; let atMillis:Double; let startMillis:Double?; let endMillis:Double?; let position:Int; let total:Int; let definitionId:String; let definitionVersion:Int; let occurrenceId:String }
/// One node on the clock orbit from the server's shared-core OrbitClock: at = where it sits, start/end = its (expected) span.
struct ClockSlot:Decodable { let id:String; let role:String; let atMillis:Double; let startMillis:Double?; let endMillis:Double? }
private struct RemoteClock:Decodable { let day:[ClockSlot]; let runs:[String:[ClockSlot]] }
private struct RemoteContext:Decodable { let workspace:RemoteWorkspace; let reservation:RemoteSelection; let day:[RemoteDayItem]?; let clock:RemoteClock?; let serverNow:Double }
private struct RemoteResult:Decodable { let accepted:Bool;let reason:String }
private struct RemoteReply:Decodable { let context:RemoteContext; let result:RemoteResult }

@MainActor private final class RemoteStore:ObservableObject {
    @Published var context:RemoteContext?
    @Published var busy=false
    @Published var error:String?
    private var readConnectionError=false
    var canRefresh:Bool {error==nil || readConnectionError}
    private var requestEpoch=0
    private let pendingURL=FileManager.default.urls(for:.applicationSupportDirectory,in:.userDomainMask)[0].appendingPathComponent(DeviceConnection.pendingFile)
    func request(_ command:[String:Any]?=nil) async {
        guard !busy else{return};readConnectionError=false;requestEpoch+=1;busy=true;defer{busy=false}
        do {
            if let command=command, !FileManager.default.fileExists(atPath:pendingURL.path) {
                try FileManager.default.createDirectory(at:pendingURL.deletingLastPathComponent(),withIntermediateDirectories:true)
                try JSONSerialization.data(withJSONObject:command).write(to:pendingURL,options:.atomic)
            }
            let pending:Data?
            do {pending=try Data(contentsOf:pendingURL)}catch let e as CocoaError where e.code == .fileReadNoSuchFile {pending=nil}
            var req=try DeviceConnection.request(pending == nil ? "context":"command")
            req.timeoutInterval=6
            if let pending=pending {req.httpMethod="POST";req.httpBody=pending;req.setValue("application/json",forHTTPHeaderField:"Content-Type");req.setValue("local",forHTTPHeaderField:"X-Routine-App")}
            let (data,response)=try await DeviceConnection.session.data(for:req)
            guard (response as? HTTPURLResponse)?.statusCode == 200 else{throw URLError(.badServerResponse)}
            if pending != nil {
                let reply=try JSONDecoder().decode(RemoteReply.self,from:data);context=reply.context
                try FileManager.default.removeItem(at:pendingURL)
                error=(reply.result.accepted || reply.result.reason=="WINDOW_ELAPSED") ? nil:L("현재 상태를 다시 확인해 주세요")
            }else{context=try JSONDecoder().decode(RemoteContext.self,from:data);error=nil}
        }catch{if !Task.isCancelled{self.error=L("연결 후 결과 확인")}}
    }
    func refresh() async {
        guard !busy,!FileManager.default.fileExists(atPath:pendingURL.path) else{return}
        let epoch=requestEpoch
        do {var req=try DeviceConnection.request("context");req.timeoutInterval=5
            let (data,response)=try await DeviceConnection.session.data(for:req);guard !busy,epoch==requestEpoch,!Task.isCancelled else{return}
            guard (response as? HTTPURLResponse)?.statusCode==200 else{throw URLError(.badServerResponse)}
            context=try JSONDecoder().decode(RemoteContext.self,from:data)
            if readConnectionError {error=nil;readConnectionError=false}
        }catch{if !Task.isCancelled,epoch==requestEpoch,!busy{readConnectionError=true;self.error=L("연결 후 결과 확인")}}
    }
    func act(_ kind:String,_ run:RemoteRun) async {
        guard let w=context?.workspace else{return}
        var c:[String:Any]=["id":UUID().uuidString,"kind":kind,"occurrenceId":run.id,"expectedRevision":run.revision,"expectedFocusRevision":w.focusRevision]
        if kind != "completeParent" {c["unitId"]=run.currentUnitId}
        await request(c)
    }
    func focus(_ run:RemoteRun) async {guard let w=context?.workspace else{return};await request(["id":UUID().uuidString,"kind":"focus","occurrenceId":run.id,"expectedRevision":w.revision])}
    func startRoutine(_ r:LibraryRoutine) async {
        guard let w=context?.workspace else{return}
        await request(["id":UUID().uuidString,"kind":"start","occurrenceId":UUID().uuidString,"expectedRevision":w.revision,"definition":["id":r.id,"version":r.version,"title":r.title,"author":r.author.name,"steps":[]]])
    }
    func start(_ x:RemoteDayItem) async {
        guard let w=context?.workspace,x.kind=="reservation" else{return}
        await request(["id":UUID().uuidString,"kind":"start","occurrenceId":x.occurrenceId,"expectedRevision":w.revision,"definition":["id":x.definitionId,"version":x.definitionVersion,"title":x.title,"author":"","steps":[]]])
    }
    func start(_ r:RemoteReservation) async {
        guard let w=context?.workspace else{return}
        await request(["id":UUID().uuidString,"kind":"start","occurrenceId":r.occurrenceId,"expectedRevision":w.revision,"definition":["id":r.definitionId,"version":r.definitionVersion,"title":r.title,"author":"","steps":[]]])
    }
}
private struct RemoteTaskView:View {
 @StateObject private var store=RemoteStore()
 @State private var together=false
 @State private var inspected:RemoteRun?
 @State private var finding=false
 @State private var dayReservation:RemoteDayItem?
 private func ordered(_ r:RemoteRun)->[OrbitNode] {(r.order ?? r.steps.map{ $0.id }).compactMap{id in r.steps.first{$0.id==id}}.map{OrbitNode(id:$0.id,title:$0.title,status:$0.status)}}
 /// Today's items in time order (server DayOrbit). An older server without "day": running runs + selected reservations.
 private func dayItems(_ c:RemoteContext)->[RemoteDayItem] {
  if let d=c.day {return d}
  let runs=c.workspace.runs.filter{$0.status=="running"&&($0.definition.windowEndMillis ?? .infinity)>c.serverNow}.map{r in let o=r.order ?? r.steps.map{$0.id};return RemoteDayItem(kind:"run",id:r.id,title:r.definition.title,atMillis:r.definition.windowStartMillis ?? c.serverNow,startMillis:r.definition.windowStartMillis,endMillis:r.definition.windowEndMillis,position:(o.firstIndex{$0==r.currentUnitId} ?? -1)+1,total:o.count,definitionId:r.definition.id,definitionVersion:r.definition.version,occurrenceId:r.id)}
  let res=c.reservation.candidates.map{x in RemoteDayItem(kind:"reservation",id:x.id,title:x.title,atMillis:x.startMillis,startMillis:x.startMillis,endMillis:x.endMillis,position:0,total:0,definitionId:x.definitionId,definitionVersion:x.definitionVersion,occurrenceId:x.occurrenceId)}
  return (runs+res).sorted{($0.atMillis,$0.kind=="run" ? 0:1)<($1.atMillis,$1.kind=="run" ? 0:1)}
 }
 private func day(_ c:RemoteContext)->[OrbitDay] {dayItems(c).map{x in
  let run=c.workspace.runs.first{$0.id==x.id && x.kind=="run"}
  let meta=x.kind=="run" ? L("진행 중")+(x.total>0 ? " · \(x.position) / \(x.total)":x.startMillis != nil ? " · "+range(x.startMillis ?? 0,x.endMillis ?? 0):""):L("시작 전")+" · "+range(x.startMillis ?? 0,x.endMillis ?? 0)
  return OrbitDay(id:x.id,kind:x.kind,title:x.title,startMillis:x.startMillis,endMillis:x.endMillis,meta:meta,steps:run.map(ordered) ?? [],progress:x.kind=="run" && x.total>0 ? "\(x.position) / \(x.total)":"")
 }}
 private func openDay(_ c:RemoteContext,_ d:OrbitDay){
  if d.kind=="run" {if c.workspace.runs.contains(where:{$0.id==d.id && $0.id != c.workspace.focusId}) {together=true;inspected=c.workspace.runs.first{$0.id==d.id}}}
  else {dayReservation=dayItems(c).first{$0.id==d.id && $0.kind=="reservation"}}
 }
 private func range(_ a:Double,_ b:Double)->String {let f=DateFormatter();f.dateFormat="HH:mm";return f.string(from:Date(timeIntervalSince1970:a/1000))+"–"+f.string(from:Date(timeIntervalSince1970:b/1000))}
 private func times(_ d:RemoteDefinition)->String {guard let a=d.windowStartMillis,let b=d.windowEndMillis else{return ""};return range(a,b)}
 var body:some View {
  ZStack {
   if let c=store.context {Group {
    let run=c.workspace.runs.first{$0.id==c.workspace.focusId}
    let active=run.map{$0.status=="running"&&($0.definition.windowEndMillis ?? .infinity)>c.serverNow} ?? false
    let others=c.workspace.runs.filter{$0.id != c.workspace.focusId&&$0.status=="running"&&($0.definition.windowEndMillis ?? .infinity)>c.serverNow}
    if let x=dayReservation {
     let open=c.serverNow>=(x.startMillis ?? .infinity) && c.serverNow<(x.endMillis ?? 0)
     APage(backLabel:L("돌아가기"),back:{dayReservation=nil},actionLabel:L("시작"),enabled:!store.busy && open,action:{Task{await store.start(x);if store.error==nil{dayReservation=nil}}}){
      Text(x.title).font(.system(size:19,weight:.semibold))
      ASource(text:L("시작 전")+" · "+range(x.startMillis ?? 0,x.endMillis ?? 0))
      if !open {Text(L("예약된 시각에 시작할 수 있어요")).font(.system(size:12)).foregroundStyle(aSlate)}
     }.id("day-reservation-\(x.id)")
    }
    else if finding {FindRoutineView(busy:store.busy || store.error != nil,back:{finding=false},start:{r in Task{await store.startRoutine(r);if store.error==nil{finding=false}}})}
    else if together {
     if let chosen=inspected,let r=others.first(where:{$0.id==chosen.id}) {
      APage(backLabel:L("돌아가기"),back:{inspected=nil},actionLabel:L("집중하기"),enabled:!store.busy,action:{Task{await store.focus(r);if store.error==nil{together=false;inspected=nil}}}){
       Text(r.definition.title).font(.system(size:19,weight:.semibold));ASource(text:r.definition.author)
       ForEach(Array(r.steps.enumerated()),id:\.element.id){i,n in Text((n.status=="completed" ? "✓":String(i+1))+" · "+n.title).font(.system(size:14)).padding(10).frame(maxWidth:.infinity,alignment:.leading).background(aSubtle,in:RoundedRectangle(cornerRadius:12))}
      }
     }else{APage(backLabel:L("현재"),back:{together=false;inspected=nil},actionLabel:L("현재"),action:{together=false;inspected=nil}){
      Text(L("함께 진행")).font(.system(size:19,weight:.semibold))
      ForEach(others){r in AStepRow(number:"›",title:r.definition.title){inspected=r}}
     }}
    }
    else if active,let r=run {
      // A plain schedule (no steps) has no step level: it stays on the day orbit and Done completes it.
      OrbitFace(parent:r.definition.title,nodes:ordered(r),currentId:r.currentUnitId,token:"\(r.id):\(r.revision):\(c.workspace.focusRevision)",busy:store.busy || store.error != nil,times:times(r.definition),startMillis:r.definition.windowStartMillis,endMillis:r.definition.windowEndMillis,clockOffset:c.serverNow-Date().timeIntervalSince1970*1000,optionsEnabled:!r.steps.isEmpty,otherCount:others.count,author:r.definition.author,description:r.definition.description ?? "",onOthers:{together=true},onFind:{finding=true},day:day(c),dayAnchor:r.id,dayOnly:r.steps.isEmpty,onDayOpen:{openDay(c,$0)},slots:c.clock?.runs[r.id] ?? [],daySlots:c.clock?.day ?? [],action:{kind in Task{await store.act(r.steps.isEmpty && kind=="complete" ? "completeParent":kind,r)}})
    }else if c.reservation.state=="conflict" {
      ReservationChoices(items:c.reservation.candidates,now:c.serverNow,busy:store.busy || store.error != nil,find:{finding=true},otherCount:others.count,others:{together=true},start:{r in Task{await store.start(r)}})
    }else if c.reservation.state=="selected",let r=c.reservation.candidates.first {
      OrbitFace(parent:r.title,nodes:[],currentId:nil,token:r.id,busy:store.busy || store.error != nil,times:range(r.startMillis,r.endMillis),startMillis:r.startMillis,endMillis:r.endMillis,clockOffset:c.serverNow-Date().timeIntervalSince1970*1000,primary:c.serverNow>=r.startMillis ? L("시작"):L("예약 예정"),optionsEnabled:false,otherCount:others.count,onOthers:{together=true},onFind:{finding=true},day:day(c),dayAnchor:r.id,dayOnly:true,onDayOpen:{openDay(c,$0)},daySlots:c.clock?.day ?? [],action:{_ in if c.serverNow>=r.startMillis {Task{await store.start(r)}}})
    }else{ScrollView{VStack(spacing:10){Text(c.reservation.state=="none" ? L("다음 작업 없음"):L("일정을 확인할 수 없어요"));Button(L("찾기")){finding=true};if !others.isEmpty{Button(L("함께 진행 {count}",["count":String(others.count)])){together=true}};Button(L("새로고침")){Task{await store.request()}}}.padding(.horizontal,20).padding(.vertical,12)}.supportViewport()}
   }.allowsHitTesting(store.error==nil).accessibilityHidden(store.error != nil)}else{ProgressView()}
   if let error=store.error {VStack(spacing:12){Text(error);Button(L("결과 확인")){Task{await store.request()}}.disabled(store.busy)}.frame(maxWidth:.infinity,maxHeight:.infinity).background(Color.white.opacity(0.97))}
  }.frame(maxWidth:.infinity,maxHeight:.infinity).background(Color.white).foregroundStyle(Color(red:20/255,green:36/255,blue:61/255)).preferredColorScheme(.light).task{await store.request();while !Task.isCancelled{try? await Task.sleep(nanoseconds:2_000_000_000);if !Task.isCancelled && store.canRefresh{await store.refresh()}}}
 }
}


private let aInk=Color(red:20/255,green:36/255,blue:61/255)
private let aNavy=Color(red:23/255,green:54/255,blue:94/255)
private let aSubtle=Color(red:242/255,green:245/255,blue:249/255)
private let aSlate=Color(red:79/255,green:97/255,blue:122/255)
private struct AAction:View {
 let label:String;var enabled=true;let action:()->Void
 var body:some View{Button(action:action){Text(label).font(.system(size:15,weight:.semibold)).foregroundStyle(.white).frame(maxWidth:.infinity).frame(height:44).background(aNavy,in:Capsule())}.buttonStyle(.plain).disabled(!enabled).accessibilityLabel(label)}
}
private struct ABack:View {let label:String;let action:()->Void
 var body:some View{Button(action:action){Image(systemName:"chevron.left").font(.system(size:18)).frame(width:44,height:44)}.buttonStyle(.plain).foregroundStyle(aNavy).accessibilityLabel(label)}
}
private struct APage<Content:View>:View {
 let backLabel:String;let back:()->Void;let actionLabel:String;var enabled=true;let action:()->Void;var current:(()->Void)?=nil;@ViewBuilder let content:()->Content
 var body:some View{GeometryReader{g in
  let w=g.size.width,h=g.size.height
  ZStack{Color.white
   ScrollView{VStack(alignment:.leading,spacing:8,content:content).frame(maxWidth:.infinity,alignment:.leading).padding(.horizontal,24).padding(.bottom,8)}.frame(height:max(48,h-122)).clipped().position(x:w/2,y:58+max(48,h-122)/2)
   ABack(label:backLabel,action:back).position(x:30,y:42)
   if let current=current{Button(L("현재"),action:current).font(.system(size:11)).buttonStyle(.plain).frame(width:64,height:44).position(x:w/2,y:42)}
   AAction(label:actionLabel,enabled:enabled,action:action).frame(width:w-64).position(x:w/2,y:h-38)
  }.foregroundStyle(aInk)
 }.ignoresSafeArea()}
}
private struct AStepRow:View {let number:String;let title:String;let action:()->Void
 var body:some View{Button(action:action){HStack(alignment:.top,spacing:8){Text(number).font(.system(size:13));Text(title).font(.system(size:14)).frame(maxWidth:.infinity,alignment:.leading)}.foregroundStyle(aInk).padding(10).frame(maxWidth:.infinity,minHeight:44,alignment:.leading).background(aSubtle,in:RoundedRectangle(cornerRadius:12))}.buttonStyle(.plain).accessibilityLabel(title)}
}
private struct ASource:View {let text:String
 var body:some View{Text(text).font(.system(size:11)).foregroundStyle(aSlate).padding(.horizontal,8).padding(.vertical,4).background(aSubtle,in:RoundedRectangle(cornerRadius:8))}
}
private func source(_ r:LibraryRoutine)->String{(r.source=="mine" ? L("내 루틴"):r.source=="collected" ? L("보관함"):L("라이브러리"))+" · "+r.author.name}
private struct FindRoutineView:View {
 @AppStorage("app.language") private var language="en"
 let busy:Bool;let back:()->Void;let start:(LibraryRoutine)->Void
 @State private var items:[LibraryRoutine]?;@State private var selected:LibraryRoutine?;@State private var stepIndex:Int?
 @State private var failed=false;@State private var attempt=0
 @State private var query="";@State private var submitted="";@State private var page=0;@State private var editing=false
 private let navy=aNavy
 var body:some View {
  Group{if let r=selected {
   APage(backLabel:L("찾기"),back:{if stepIndex != nil{stepIndex=nil}else{selected=nil}},actionLabel:busy ? L("시작 중"):L("시작"),enabled:!busy,action:{start(r)},current:back){
    Text(stepIndex.map{r.steps[$0].title} ?? r.title).font(.system(size:19,weight:.semibold))
    ASource(text:source(r))
    if let i=stepIndex{if let copy=r.steps[i].description,!copy.isEmpty{Text(copy).font(.system(size:14))};AStepRow(number:"‹",title:r.title){stepIndex=nil}}else{
     ForEach(Array(r.steps.enumerated()),id:\.element.id){i,step in AStepRow(number:String(i+1),title:step.title){stepIndex=i}}
     if !(r.reason ?? r.description).isEmpty{Text(r.reason ?? r.description).font(.system(size:14)).foregroundStyle(aSlate)}
    }
   }.id("detail-\(r.id)-\(stepIndex ?? -1)")
  }else if editing {
   APage(backLabel:L("돌아가기"),back:{editing=false},actionLabel:L("찾기"),enabled:!busy,action:{submitted=query.trimmingCharacters(in:.whitespacesAndNewlines);editing=false;attempt+=1},current:back){
    Text(L("어떤 루틴을 찾으세요?")).font(.system(size:18,weight:.semibold))
    TextField(text:$query,prompt:Text(L("말하거나 입력")).foregroundStyle(aSlate)){Text(L("말하거나 입력"))}.foregroundStyle(aInk).padding(.horizontal,4).frame(minHeight:44).background(aSubtle,in:RoundedRectangle(cornerRadius:12)).accessibilityLabel(L("검색 내용")).onChange(of:query){_,value in if value.count>500{query=String(value.prefix(500))}}
    if !query.isEmpty{Text(query).font(.system(size:14))}
    Text(L("막막하다면 지금 상황을 말해도 좋아요")).font(.system(size:12)).foregroundStyle(aSlate)
    AStepRow(number:"◎",title:L("언어")+": "+(appLanguages[language] ?? "English")){let codes=appLanguages.keys.sorted();language=codes[((codes.firstIndex(of:language) ?? 0)+1)%codes.count]}
   }
  }else {
   RoutineDeck(items:items,page:$page,failed:failed,busy:busy,query:submitted,back:back,edit:{editing=true},retry:{attempt+=1},open:{selected=$0;stepIndex=nil},start:start)
  }}
  .foregroundStyle(navy).task(id:attempt){failed=false;items=nil;page=0;do{var req=try DeviceConnection.request("search");req.timeoutInterval=5;req.httpMethod="POST";req.setValue("application/json",forHTTPHeaderField:"Content-Type");req.setValue("local",forHTTPHeaderField:"X-Routine-App");req.httpBody=try JSONSerialization.data(withJSONObject:["query":submitted]);let(data,response)=try await DeviceConnection.session.data(for:req);guard (response as? HTTPURLResponse)?.statusCode==200 else{throw URLError(.badServerResponse)};let result=try JSONDecoder().decode(LibraryReply.self,from:data);guard !Task.isCancelled else{return};items=result.items}catch{if !Task.isCancelled{failed=true}}}
 }
}
private struct RoutineDeck:View {
 let items:[LibraryRoutine]?;@Binding var page:Int;let failed:Bool;let busy:Bool;let query:String
 let back:()->Void;let edit:()->Void;let retry:()->Void;let open:(LibraryRoutine)->Void;let start:(LibraryRoutine)->Void
 @State private var crown=0.0;@State private var lastCrown=0.0
 @FocusState private var crownFocused:Bool
 private var count:Int{items?.count ?? 0}
 private func move(_ delta:Int){guard count>0 else{return};page=min(max(0,page+delta),count-1)}
 var body:some View{GeometryReader{g in
  let w=g.size.width,h=g.size.height,ch=h*0.36,cy=h*0.44+(page>0 ? 8:0)
  ZStack{Color.white
   ABack(label:L("돌아가기"),action:back).position(x:30,y:42)
   Button(L("현재"),action:back).font(.system(size:11)).buttonStyle(.plain).frame(width:64,height:44).position(x:w/2,y:42)
   Button(action:edit){Image(systemName:"magnifyingglass").frame(width:44,height:44)}.buttonStyle(.plain).position(x:w-30,y:48).accessibilityLabel(L("검색 입력"))
   if failed || items == nil || count==0 {VStack(spacing:8){Text(failed ? L("연결을 확인해 주세요"):items == nil ? L("찾는 중"):L("맞는 루틴이 없어요")).multilineTextAlignment(.center)
    if failed{Button(L("다시"),action:retry)}
    if items != nil && count==0 && !failed{Button(L("더 자세하게"),action:edit)}
   }.padding(.horizontal,30)}else if let items=items{
    let near=Array([page-1,page+1,page+2].filter{items.indices.contains($0)}.prefix(2))
    ForEach(Array(near.reversed()),id:\.self){index in
     let delta=index<page ? -1:index-page
     VStack{if delta>0{Spacer(minLength:0)};Text(items[index].title).font(.system(size:10)).lineLimit(1).padding(.horizontal,10).padding(.vertical,2);if delta<0{Spacer(minLength:0)}}.frame(width:w-80,height:ch).background(Color(red:213/255,green:223/255,blue:236/255).opacity(delta==2 ? 0.5:1),in:RoundedRectangle(cornerRadius:14)).position(x:w/2,y:cy+Double(delta<0 ? -14:12*delta)).accessibilityHidden(true)
    }
    let r=items[min(page,count-1)]
    Button(action:{open(r)}){VStack(alignment:.leading,spacing:3){Text(r.title).font(.system(size:15,weight:.semibold)).lineLimit(2);Text(source(r)).font(.system(size:10)).lineLimit(1).foregroundStyle(aSlate);if ch>=78 && !(r.reason ?? r.description).isEmpty{Text(r.reason ?? r.description).font(.system(size:11)).lineLimit(1).foregroundStyle(aSlate)}}.frame(width:w-84,height:ch-12,alignment:.topLeading).padding(.horizontal,12).padding(.vertical,6).background(aSubtle,in:RoundedRectangle(cornerRadius:16))}
     .buttonStyle(.plain).position(x:w/2,y:cy).disabled(busy).accessibilityLabel(L("루틴: ")+r.title).accessibilityAction(named:Text(L("다음 추천"))){move(1)}.accessibilityAction(named:Text(L("이전 추천"))){move(-1)}
    AAction(label:busy ? L("시작 중"):L("시작"),enabled:!busy,action:{start(r)}).frame(width:w-64).position(x:w/2,y:h-38)
   }
  }.foregroundStyle(aInk).clipped().contentShape(Rectangle())
   .highPriorityGesture(DragGesture(minimumDistance:24).onEnded{v in if abs(v.translation.height)>abs(v.translation.width){move(v.translation.height<0 ? 1:-1)}})
   .focusable().focused($crownFocused).onAppear{crownFocused=true}.digitalCrownRotation($crown,from:-1000,through:1000,by:1,sensitivity:.low,isContinuous:false,isHapticFeedbackEnabled:true)
   .onChange(of:crown){_,v in if abs(v-lastCrown)>=1{move(v<lastCrown ? 1:-1);lastCrown=v}}
 }.ignoresSafeArea().preferredColorScheme(.light)}
}

private struct TitleHeightKey:PreferenceKey {static var defaultValue=0.0;static func reduce(value:inout Double,nextValue:()->Double){value=max(value,nextValue())}}
private struct OrbitNode:Identifiable {let id:String;let title:String;let status:String}
/// A "My routine" item: a running routine (steps = its mini ring) or a reservation.
private struct OrbitDay:Identifiable {let id:String;let kind:String;let title:String;let startMillis:Double?;let endMillis:Double?;let meta:String;let steps:[OrbitNode]
 /// Watch-size step progress ("2 / 3"), placed like the step level's counter; the full meta is the accessibility label.
 var progress:String=""}
private struct OrbitFace:View {
    let parent:String;let nodes:[OrbitNode];let currentId:String?;let token:String;let busy:Bool
    var times:String="";var startMillis:Double?=nil;var endMillis:Double?=nil
    /// App-server time minus this device's clock (ms), so window progress follows the server, not the watch.
    var clockOffset:Double=0;var primary:String=L("완료");var optionsEnabled=true;var otherCount=0
    var author:String="";var description:String=""
    var onOthers:()->Void={};var onFind:(()->Void)?=nil
    /// Day level ("My routine"): today's items; the anchor is the real focus (run) or the selected reservation.
    /// Browsing it is preview only. dayOnly = there is no step level (a reservation not started yet).
    var day:[OrbitDay]=[];var dayAnchor:String?=nil;var dayOnly=false;var onDayOpen:(OrbitDay)->Void={_ in}
    /// Clock orbit (user 11-04): this run's steps and the day's items placed at their times by the shared core (OrbitClock).
    /// Empty (local demo / older server): the step level keeps its fixed neighbour slots.
    var slots:[ClockSlot]=[];var daySlots:[ClockSlot]=[]
    let action:(String)->Void
    @State private var dayBrowse:Int?
    @State private var browsing:Int?;@State private var root=OrbitFace.verificationDay;@State private var detail=false;@State private var detailStep:Int?
    @State private var overlay=false;@State private var selection = -1
    @State private var turn=0.0;@State private var orbitStep=9.0;@State private var lastParent="";@State private var clock=Date()
    @State private var crown=0.0;@State private var lastCrown=0.0;@State private var titleHeight=0.0
    @State private var contact:String?;@State private var began:CGPoint = .zero;@State private var moved=false
    @State private var hold=WatchHold();@State private var timer:Task<Void,Never>?
    @State private var held=false;@State private var wasOverlay=false
    @Environment(\.scenePhase) private var phase
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    private let ink=Color(red:20/255,green:36/255,blue:61/255)
    private let navy=Color(red:23/255,green:54/255,blue:94/255)
    private let slate=Color(red:79/255,green:97/255,blue:122/255)
    private let pale=Color(red:213/255,green:223/255,blue:236/255)
    private let geometry=WatchGeometry()
    private var actual:Int {nodes.firstIndex{$0.id==currentId} ?? 0}
    private var shown:Int {min(max(0,browsing ?? actual),max(0,nodes.count-1))}
    private var dayMode:Bool {(root || dayOnly) && !day.isEmpty}
    private var dayActual:Int {day.firstIndex{$0.id==dayAnchor} ?? 0}
    private var dayShown:Int {min(max(0,dayBrowse ?? dayActual),max(0,day.count-1))}
    private var dayBrowsing:Bool {dayMode && dayShown != dayActual}
    private var shownDay:OrbitDay? {dayMode ? day[dayShown]:nil}
    private var winStart:Double? {dayMode ? shownDay?.startMillis:startMillis}
    private var winEnd:Double? {dayMode ? shownDay?.endMillis:endMillis}
    /// Step mini ring. On the watch the day neighbours sit one slot (~24pt) from the planet, so the ring is drawn only
    /// when no neighbour is (time window shown or a single item); "2 / 3" carries the step progress instead.
    private var ring:[OrbitNode] {dayMode ? (windowShown || day.count<2 ? (shownDay?.steps ?? []):[]):root ? nodes:[]}
    private var returning:Bool {browsing != nil || dayBrowsing || (root && !optionsEnabled)}
    private var title:String {if let d=shownDay{return d.title};return root || nodes.isEmpty ? parent:nodes[shown].title}
    private var windowShown:Bool {(dayMode || root || (primary==L("시작")||primary==L("예약 예정"))) && (winStart ?? 0)<(winEnd ?? 0)}
    /// Time scale by depth from the shared core (OrbitScales): My routine = 2 h window, 10-min ticks; a routine's steps = 30 min, 5-min ticks.
    /// Now (the node) sits at 0°, now − window/2 at the top end, now + window/2 at the bottom end; ticks are on real clock times.
    private var scale:OrbitScale {dayMode ? OrbitScales.shared.DAY : OrbitScales.shared.ROUTINE}
    private var windowMillis:Double {Double(scale.halfWindowMillis)}
    private var clockTicks:[OrbitTick] {OrbitScales.shared.ticks(scale:scale,nowMillis:Int64(nowMillis),zoneOffsetMillis:Int64(TimeZone.current.secondsFromGMT(for:clock)*1000))}
    private var nowMillis:Double {clock.timeIntervalSince1970*1000+clockOffset}
    /// Watch layout (user 11-04, clock2): a one-line title tight under the top bar (search / +N) and a short capsule near
    /// the bottom edge, so the clock orbit between them gets about twice the height.
    private static func titleY(_ h:Double)->Double {h<215 ? 43:45}
    private static let titleBox=20.0,ctaHeight=36.0
    private static func footerY(_ h:Double)->Double {h-(h<215 ? 26:29)}
    /// Half the window in degrees, sized so both ends (and their labels) stay clear of the title and the button.
    private func halfSpan(w:Double,h:Double,footer:Double)->Double {
        // The title is vertically centred in its frame; use its measured height (fallback: the full frame).
        let top=OrbitFace.titleY(h)+min(titleHeight>0 ? titleHeight:99,OrbitFace.titleBox)/2+6,bottom=footer-OrbitFace.ctaHeight/2-6
        return asin(min(1,max(0,min(h/2-top,bottom-h/2))/(w/2)))*180/Double.pi
    }
    private func windowAngle(_ t:Double,_ half:Double)->Double {(t-nowMillis)/windowMillis*half}
    private func orbitPoint(_ deg:Double,_ w:Double,_ h:Double,_ radius:Double?=nil)->CGPoint {let a=deg*Double.pi/180,r=radius ?? w/2;return CGPoint(x:r*cos(a),y:h/2+r*sin(a))}
    /// Window-end times (slate, left of the orbit) and reservation start/end (navy, right of the orbit, clear of the node and "+1").
    private func windowLabels(w:Double,h:Double,footer:Double)->(ends:[(String,CGPoint)],marks:[(String,CGPoint)]) {
        guard windowShown,let a=winStart,let b=winEnd else{return ([],[])}
        let f=DateFormatter();f.dateFormat="HH:mm";let half=halfSpan(w:w,h:h,footer:footer),r=w/2,lh=9.0
        let text={(t:Double) in f.string(from:Date(timeIntervalSince1970:t/1000))}
        // hour / quarter-hour labels on the sliding clock ticks (kept clear of the node), instead of fixed end times
        let ends=clockTicks.filter{$0.label}.map{k in (text(Double(k.atMillis)),orbitPoint(k.offset*half,w,h))}.filter{abs($0.1.y-h/2)>12+lh}
        var marks:[(String,CGPoint)]=[]
        for (t,upward) in [(a,a<=nowMillis),(b,b<nowMillis)] where abs(windowAngle(t,half))<=half {
            var y=orbitPoint(windowAngle(t,half),w,h).y
            if abs(y-h/2)<15+lh {y=h/2+(upward ? -1:1)*(15+lh)} // clear of the app-time label right of the planet
            let near=max(0,abs(y-h/2)-lh)
            marks.append((text(t),CGPoint(x:sqrt(max(0,r*r-near*near))+10,y:y)))
        }
        if marks.count==2 && abs(marks[0].1.y-marks[1].1.y)<2*lh {marks.removeLast()}
        return (ends,marks)
    }
    /// Nodes on the clock (not the current one, which is the planet = now), and the current item's timer span.
    private var clockNodes:[(at:Double,fill:Color,done:Bool,selected:Bool)] {
        if dayMode {return daySlots.filter{$0.role != "current"}.map{s in let i=day.firstIndex{$0.id==s.id};return (s.atMillis,day.first{$0.id==s.id}?.kind=="run" ? pale:Color.white,false,i != nil && i==dayShown && dayBrowsing)}}
        if root {return []}
        return slots.filter{$0.role != "current"}.map{s in let i=nodes.firstIndex{$0.id==s.id};return (s.atMillis,s.role=="done" ? navy:pale,s.role=="done",i != nil && browsing != nil && i==shown)}
    }
    /// Display only: nodes within the planet are nudged just above (past) / below (future) it, one node apart, keeping their order.
    private func spreadAngles(_ a:[Double],clear:Double,gap:Double)->[Double] {
        var out=a
        for sign in [1.0,-1.0] {
            var last:Double?=nil
            for i in a.indices.filter({a[$0]*sign>=0 && (sign>0 || a[$0] != 0)}).sorted(by:{abs(a[$0])<abs(a[$1])}) {
                var v=max(abs(a[i]),clear);if let l=last {v=max(v,l+gap)};last=v;out[i]=sign*v
            }
        }
        return out
    }
    /// Simulator verification only (-verification-port 8793 -verification-day): open on the day level ("My routine") for screenshots.
    private static var verificationDay:Bool {
        #if DEBUG && targetEnvironment(simulator)
        return DeviceConnection.localPort==8793 && ProcessInfo.processInfo.arguments.contains("-verification-day")
        #else
        return false
        #endif
    }
    private var timerSlot:ClockSlot? {dayMode ? daySlots.first{$0.role=="current"}:root ? nil:slots.first{$0.role=="current"}}
    private var nowText:String {let f=DateFormatter();f.dateFormat="HH:mm";return f.string(from:Date(timeIntervalSince1970:nowMillis/1000))}
    private func home(){cancel();browsing=nil;root=false;detail=false;dayBrowse=nil}
    /// Day level → down: the anchor run goes to its steps; other items open their detail (Focus here / Start).
    private func openDay(){guard let d=shownDay else{return};if d.id==dayAnchor && !dayOnly && !nodes.isEmpty{root=false;dayBrowse=nil}else{onDayOpen(d)}}
    private func back(){if dayBrowsing{dayBrowse=nil}else{home()}}
    private func cancel(){timer?.cancel();timer=nil;contact=nil;hold.cancel();held=false;overlay=false;selection = -1}
    private func peer(_ delta:Int){if dayMode{let n=min(max(0,dayShown+delta),day.count-1);dayBrowse=n==dayActual ? nil:n;return};guard !root,!nodes.isEmpty else{return};let n=min(max(0,shown+delta),nodes.count-1);browsing=n==actual ? nil:n}
    private func run(_ index:Int){guard !busy else{return};overlay=false;selection = -1;if index==0{action(root ? "completeParent":"complete")}else if !root{action(index==1 ? "defer":"skip")}}
    var body:some View {
        GeometryReader { proxy in
            let w=proxy.size.width,h=proxy.size.height,footer=OrbitFace.footerY(h),bw=w-72,ctaX=w/2
            ZStack {
                Color.white
                if detail {
                    APage(backLabel:L("돌아가기"),back:{if detailStep != nil{detailStep=nil}else{home()}},actionLabel:L("현재"),enabled:!busy,action:home){
                        Text(detailStep.map{nodes[$0].title} ?? parent).font(.system(size:19,weight:.semibold))
                        if !author.isEmpty{ASource(text:author)}
                        if let i=detailStep {
                            if nodes[i].status=="completed"{ASource(text:L("완료"))}
                            if nodes[i].status=="skipped"{ASource(text:L("건너뜀"))}
                            if nodes[i].status=="elapsed"{ASource(text:L("시간 경과"))}
                            AStepRow(number:"‹",title:parent){detailStep=nil}
                        }else{
                            ForEach(Array(nodes.enumerated()),id:\.element.id){i,n in AStepRow(number:n.status=="completed" ? "✓":n.status=="skipped" ? "↦":n.status=="elapsed" ? "◷":String(i+1),title:n.title){detailStep=i}}
                            if !description.isEmpty{Text(description).font(.system(size:14)).foregroundStyle(aSlate)}
                            if !times.isEmpty{Text(times).font(.system(size:12)).foregroundStyle(aSlate)}
                        }
                    }.id("current-detail-\(detailStep ?? -1)")

                }else{
                    ZStack {
                        Canvas {ctx,size in
                            let c=CGPoint(x:w/2,y:h/2)
                            if !root && !nodes.isEmpty {
                                ctx.fill(Path(ellipseIn:CGRect(x:-22,y:h/2-22,width:44,height:44)),with:.color(aSubtle))
                                ctx.stroke(Path(ellipseIn:CGRect(x:-22,y:h/2-22,width:44,height:44)),with:.color(pale),lineWidth:1)
                                var path=Path();path.addArc(center:CGPoint(x:0,y:h/2),radius:w/2,startAngle:.degrees(-2*geometry.peerAngle(width:w)-2),endAngle:.degrees(2*geometry.peerAngle(width:w)+2),clockwise:false)
                                ctx.stroke(path,with:.color(Color(red:113/255,green:133/255,blue:158/255)),lineWidth:1.5)
                                for delta in [-2,-1,1,2] where slots.isEmpty && nodes.indices.contains(shown+delta) && geometry.peerVisible(width:w,height:h,offset:Int32(delta),subtitle:browsing != nil) {
                                    let p=CGPoint(x:geometry.x(width:w,angleDegrees:Double(delta)*geometry.peerAngle(width:w)),y:geometry.y(width:w,height:h,angleDegrees:Double(delta)*geometry.peerAngle(width:w)))
                                    let done=nodes[shown+delta].status=="completed"
                                    ctx.fill(Path(ellipseIn:CGRect(x:p.x-7,y:p.y-7,width:14,height:14)),with:.color(done ? navy:pale))
                                    ctx.stroke(Path(ellipseIn:CGRect(x:p.x-7,y:p.y-7,width:14,height:14)),with:.color(slate),lineWidth:1)
                                    if done {var check=Path();check.move(to:CGPoint(x:p.x-3,y:p.y));check.addLine(to:CGPoint(x:p.x-1,y:p.y+2));check.addLine(to:CGPoint(x:p.x+3,y:p.y-3));ctx.stroke(check,with:.color(.white),lineWidth:1)}
                                }
                            } else if dayMode {
                                // Same parent sphere and orbit as the step level; the sphere is "My routine".
                                ctx.fill(Path(ellipseIn:CGRect(x:-22,y:h/2-22,width:44,height:44)),with:.color(aSubtle))
                                ctx.stroke(Path(ellipseIn:CGRect(x:-22,y:h/2-22,width:44,height:44)),with:.color(pale),lineWidth:1)
                                if !windowShown && daySlots.isEmpty {
                                    var path=Path();path.addArc(center:CGPoint(x:0,y:h/2),radius:w/2,startAngle:.degrees(-2*geometry.peerAngle(width:w)-2),endAngle:.degrees(2*geometry.peerAngle(width:w)+2),clockwise:false)
                                    ctx.stroke(path,with:.color(Color(red:113/255,green:133/255,blue:158/255)),lineWidth:1.5)
                                    // Neighbour day items (runs filled, reservations hollow). Hidden under a time window so they never read as times.
                                    for delta in [-2,-1,1,2] where day.indices.contains(dayShown+delta) && geometry.peerVisible(width:w,height:h,offset:Int32(delta),subtitle:false) {
                                        let p=CGPoint(x:geometry.x(width:w,angleDegrees:Double(delta)*geometry.peerAngle(width:w)),y:geometry.y(width:w,height:h,angleDegrees:Double(delta)*geometry.peerAngle(width:w)))
                                        ctx.fill(Path(ellipseIn:CGRect(x:p.x-7,y:p.y-7,width:14,height:14)),with:.color(day[dayShown+delta].kind=="run" ? pale:.white))
                                        ctx.stroke(Path(ellipseIn:CGRect(x:p.x-7,y:p.y-7,width:14,height:14)),with:.color(slate),lineWidth:1)
                                    }
                                }
                            }
                        }.rotationEffect(.degrees(root ? 0:turn),anchor:UnitPoint(x:0,y:0.5)).mask { Rectangle().frame(height:max(0,footer-OrbitFace.ctaHeight/2-4-(OrbitFace.titleY(h)+OrbitFace.titleBox/2+2))).position(x:w/2,y:(footer-OrbitFace.ctaHeight/2-4+OrbitFace.titleY(h)+OrbitFace.titleBox/2+2)/2) }.accessibilityHidden(true)
                        Canvas {ctx,size in
                            let c=CGPoint(x:w/2,y:h/2)
                            if windowShown,let a=winStart,let b=winEnd {
                                let half=halfSpan(w:w,h:h,footer:footer),sa=max(-half,windowAngle(a,half)),ea=min(half,windowAngle(b,half))
                                func orbit(_ from:Double,_ to:Double,_ color:Color,_ width:Double){guard to>from else{return};var arc=Path();arc.addArc(center:CGPoint(x:0,y:h/2),radius:w/2,startAngle:.degrees(from),endAngle:.degrees(to),clockwise:false);ctx.stroke(arc,with:.color(color),lineWidth:width)}
                                orbit(-half,half,pale,1.5)
                                orbit(sa,min(0,ea),slate,6);orbit(max(0,sa),ea,Color(red:163/255,green:179/255,blue:201/255),6)
                                func tick(_ deg:Double,_ len:Double,_ color:Color){var t=Path();t.move(to:orbitPoint(deg,w,h,w/2-len));t.addLine(to:orbitPoint(deg,w,h,w/2+len));ctx.stroke(t,with:.color(color),lineWidth:1.5)}
                                for k in clockTicks {tick(k.offset*half,k.label ? 4:2.5,slate)}
                                for t in [a,b] where abs(windowAngle(t,half))<=half {tick(windowAngle(t,half),6,ink)}
                            }
                            // Clock ticks are always on the orbit (user 11-04), even with no time window: the orbit is a clock at every depth.
                            if !windowShown && (!nodes.isEmpty || root || dayMode) {
                                let half=halfSpan(w:w,h:h,footer:footer)
                                for k in clockTicks {let len=k.label ? 4.0:2.5;var t=Path();t.move(to:orbitPoint(k.offset*half,w,h,w/2-len));t.addLine(to:orbitPoint(k.offset*half,w,h,w/2+len));ctx.stroke(t,with:.color(slate),lineWidth:1.5)}
                            }
                            // Clock orbit: the current item's timer (thin dark elapsed, thick remaining) and every other node at its time.
                            if !slots.isEmpty || !daySlots.isEmpty {
                                let half=halfSpan(w:w,h:h,footer:footer)
                                func arc(_ from:Double,_ to:Double,_ color:Color,_ width:Double){guard to>from else{return};var p=Path();p.addArc(center:CGPoint(x:0,y:h/2),radius:w/2,startAngle:.degrees(from),endAngle:.degrees(to),clockwise:false);ctx.stroke(p,with:.color(color),lineWidth:width)}
                                if !windowShown {arc(-half,half,pale,1.5)}
                                if let t=timerSlot,let a=t.startMillis,let b=t.endMillis,b>nowMillis {
                                    // The remaining part starts at the planet's edge (not its centre) so a few-minute remainder is not hidden under it.
                                    let edge=13.0/(w/2)*180/Double.pi
                                    arc(max(-half,windowAngle(a,half)),0,ink,2);arc(edge,min(half+edge,edge+windowAngle(b,half)),Color(red:243/255,green:138/255,blue:32/255).opacity(0.7),6)
                                }
                                let shownNodes=clockNodes.filter{abs(windowAngle($0.at,half))<=half}
                                let angles=spreadAngles(shownNodes.map{windowAngle($0.at,half)},clear:(ring.isEmpty ? 21.0:38.0)/(w/2)*180/Double.pi,gap:15.0/(w/2)*180/Double.pi)
                                for (n,deg) in zip(shownNodes,angles) {
                                    let p=orbitPoint(deg,w,h),r=n.selected ? 8.0:6.5
                                    ctx.fill(Path(ellipseIn:CGRect(x:p.x-r,y:p.y-r,width:2*r,height:2*r)),with:.color(n.fill))
                                    ctx.stroke(Path(ellipseIn:CGRect(x:p.x-r,y:p.y-r,width:2*r,height:2*r)),with:.color(n.selected ? Color(red:243/255,green:138/255,blue:32/255):slate),lineWidth:n.selected ? 2:1)
                                    if n.done {var check=Path();check.move(to:CGPoint(x:p.x-3,y:p.y));check.addLine(to:CGPoint(x:p.x-1,y:p.y+2));check.addLine(to:CGPoint(x:p.x+3,y:p.y-3));ctx.stroke(check,with:.color(.white),lineWidth:1)}
                                }
                            }
                            if !nodes.isEmpty || root || dayMode || (primary==L("시작")||primary==L("예약 예정")) {
                                ctx.fill(Path(ellipseIn:CGRect(x:c.x-12,y:c.y-12,width:24,height:24)),with:.color(.white))
                                ctx.fill(Path(ellipseIn:CGRect(x:c.x-9,y:c.y-9,width:18,height:18)),with:.color(Color(red:243/255,green:138/255,blue:32/255)))
                                ctx.stroke(Path(ellipseIn:CGRect(x:c.x-12,y:c.y-12,width:24,height:24)),with:.color(Color(red:140/255,green:77/255,blue:0)),lineWidth:1)
                            }
                            if !ring.isEmpty {
                                let rr=32.0
                                ctx.stroke(Path(ellipseIn:CGRect(x:c.x-rr,y:c.y-rr,width:2*rr,height:2*rr)),with:.color(pale),lineWidth:1)
                                for (i,n) in ring.prefix(3).enumerated(){let a=Double(-160+i*160)*Double.pi/180;let p=CGPoint(x:c.x+rr*cos(a),y:c.y+rr*sin(a));ctx.fill(Path(ellipseIn:CGRect(x:p.x-3,y:p.y-3,width:6,height:6)),with:.color(n.status=="completed" ? navy:pale))}
                            }
                        }.accessibilityHidden(true)
                        Text(title).font(.system(size:15,weight:.semibold)).lineLimit(1).truncationMode(.tail).multilineTextAlignment(.leading).foregroundStyle(ink).background(GeometryReader{g in Color.clear.preference(key:TitleHeightKey.self,value:g.size.height)}).frame(width:w-40,height:OrbitFace.titleBox,alignment:.leading).contentShape(Rectangle()).onTapGesture{if dayMode{openDay()}else{detailStep=root || nodes.isEmpty ? nil:shown;detail=true}}.accessibilityLabel(L("상세: ")+title).accessibilityAddTraits(.isButton).position(x:w/2,y:OrbitFace.titleY(h)).onPreferenceChange(TitleHeightKey.self){titleHeight=$0}
                        if let d=shownDay {if !windowShown && !d.progress.isEmpty {Text(d.progress).font(.system(size:11)).monospacedDigit().foregroundStyle(slate).position(x:38,y:h/2+26).accessibilityLabel(d.meta)}}
                        else if browsing != nil || !(root || (primary==L("시작")||primary==L("예약 예정"))) {Text(browsing != nil ? L("탐색 중") : "\(shown+1) / \(nodes.count)").font(.system(size:11)).monospacedDigit().foregroundStyle(slate).position(x:38,y:h/2+26)}
                        else if !windowShown && !times.isEmpty {Text(times).font(.system(size:11)).monospacedDigit().foregroundStyle(slate).position(x:w/2,y:footer-OrbitFace.ctaHeight/2-10)}
                        let labels=windowLabels(w:w,h:h,footer:footer)
                        ForEach(Array(labels.ends.enumerated()),id:\.offset){_,label in Text(label.0).font(.system(size:11)).monospacedDigit().foregroundStyle(slate).fixedSize().frame(width:max(0,label.1.x-8),alignment:.trailing).position(x:max(0,label.1.x-8)/2,y:label.1.y)}
                        ForEach(Array(labels.marks.enumerated()),id:\.offset){_,label in Text(label.0).font(.system(size:h<215 ? 13:14,weight:.semibold)).monospacedDigit().foregroundStyle(navy).fixedSize().frame(width:max(0,w-label.1.x-4),alignment:.leading).position(x:label.1.x+max(0,w-label.1.x-4)/2,y:label.1.y)}
                        if dayMode {Text(L("나의 루틴")).font(.system(size:11)).foregroundStyle(slate).lineLimit(2).frame(width:w/2-34,height:24,alignment:.leading).contentShape(Rectangle()).onTapGesture{dayBrowse=nil}.position(x:12+(w/2-34)/2,y:h/2).accessibilityAddTraits(.isButton).accessibilityLabel(L("나의 루틴"))}
                        else if !root && !nodes.isEmpty {Text(parent).font(.system(size:11)).foregroundStyle(slate).lineLimit(2).frame(width:w/2-34,height:24,alignment:.leading).contentShape(Rectangle()).onTapGesture{root=true;dayBrowse=nil}.position(x:12+(w/2-34)/2,y:h/2).accessibilityAddTraits(.isButton).accessibilityLabel(L("상위: ")+parent)}
                        // The app's time (server clock) right of the planet = now. "+N" lives in the top bar next to search.
                        if !nodes.isEmpty || root || dayMode || (primary==L("시작")||primary==L("예약 예정")) {Text(nowText).font(.system(size:h<215 ? 13:14,weight:.bold)).monospacedDigit().foregroundStyle(ink).fixedSize().position(x:w/2+(ring.isEmpty ? 16:38)+20,y:h/2).accessibilityLabel(nowText)}
                        if otherCount>0 {Button("+\(otherCount)",action:onOthers).buttonStyle(.plain).font(.system(size:15,weight:.semibold)).foregroundStyle(navy).frame(width:40,height:40).position(x:onFind != nil ? 66:24,y:22).accessibilityLabel(L("함께 진행 {count}",["count":String(otherCount)]))}
                        if let onFind=onFind {Button(action:onFind){Image(systemName:"magnifyingglass").frame(width:44,height:44)}.buttonStyle(.plain).foregroundStyle(navy).position(x:24,y:22).disabled(busy).accessibilityLabel(L("찾기"))}
                        Text(busy ? L("저장 중"):returning ? L("현재"):primary==L("완료") ? L("✓ 완료"):primary).font(.system(size:15,weight:.semibold)).foregroundStyle(.white).frame(width:bw,height:OrbitFace.ctaHeight).background(busy ? pale:navy,in:Capsule()).position(x:ctaX,y:footer).accessibilityAction(named:Text(L("작업 옵션"))){if optionsEnabled && !busy{overlay=true}}.accessibilityLabel(returning ? L("현재"):primary).accessibilityAddTraits(.isButton).accessibilityAction{if !busy{if returning{back()}else{action(root ? "completeParent":(primary==L("시작")||primary==L("예약 예정")) ? "start":"complete")}}}
                    }.blur(radius:overlay ? 6:0).accessibilityHidden(overlay)
                    if overlay {
                        Text(selection>=0 ? [L("완료"),L("미루기"),L("건너뛰기")][selection]:"").font(.system(size:16,weight:.semibold)).foregroundStyle(ink).position(x:w/2,y:h*0.22).accessibilityAction(named:Text(L("돌아가기"))){overlay=false}
                        ForEach(0..<3,id:\.self){i in Image(systemName:["checkmark","arrow.uturn.forward","forward.end"][i]).font(.system(size:20,weight:.semibold)).foregroundStyle(selection==i ? .white:ink).frame(width:44,height:44).background(selection==i ? navy:Color.white,in:Circle()).overlay(Circle().stroke(slate,lineWidth:1)).position(x:w/2+Double(i-1)*52,y:h*0.38).accessibilityLabel([L("완료"),L("미루기"),L("건너뛰기")][i]).accessibilityAddTraits(.isButton).accessibilityAction{run(i)}}
                    }
                }
            }.contentShape(Rectangle()).coordinateSpace(name:"orbit").simultaneousGesture(DragGesture(minimumDistance:0,coordinateSpace:.named("orbit")).onChanged { v in
                guard !busy,!detail else{return}
                if contact==nil {contact=token;began=v.startLocation;moved=false;held=false;wasOverlay=overlay
                    hold.begin(target:token,at:0,startX:began.x,startY:began.y)
                    let isButton=abs(began.y-footer)<24 && abs(began.x-ctaX)<bw/2
                    if isButton && !returning && primary==L("완료") && optionsEnabled {timer=Task{@MainActor in
                        try? await Task.sleep(nanoseconds:450_000_000)
                        guard !Task.isCancelled,contact==token,hold.activate(at:450) else{return};held=true;overlay=true;selection = -1;WKInterfaceDevice.current().play(.click)
                    }}
                }
                if hypot(v.location.x-began.x,v.location.y-began.y)>12{moved=true}
                hold.move(px:v.location.x,py:v.location.y)
                if held {let i=Int(geometry.option(width:w,height:h,x:v.location.x,y:v.location.y));selection=root&&i>0 ? -1:i}
            }.onEnded{v in
                guard let original=contact else{return};timer?.cancel();timer=nil;contact=nil
                guard original==token,!busy else{cancel();return}
                if held {let choice=Int(hold.finish(target:token,option:Int32(selection)));held=false;overlay=false;selection = -1;if choice>=0{run(choice)};return}
                hold.cancel()
                if wasOverlay {let i=Int(geometry.option(width:w,height:h,x:v.location.x,y:v.location.y));overlay=false;if i>=0 && (!root||i==0){run(i)};return}
                let dx=v.location.x-began.x,dy=v.location.y-began.y
                if max(abs(dx),abs(dy))>35 {if abs(dy)>abs(dx){peer(dy<0 ? 1:-1)}else if dayMode{if dx<0{openDay()}}else{root=dx>0;dayBrowse=nil};return}
                if !moved && abs(began.y-footer)<24 && abs(began.x-ctaX)<bw/2 {if returning{back()}else{action(root ? "completeParent":(primary==L("시작")||primary==L("예약 예정")) ? "start":"complete")}}
                else if !moved && dayMode && abs(began.x-w/2)<24 && abs(began.y-h/2)<24 {openDay()}
                else if !moved && abs(began.x-w/2)<24 && abs(began.y-h/2)<24 && optionsEnabled && browsing==nil {overlay=true}
            })
            .onAppear{orbitStep=geometry.peerAngle(width:w)}
            .focusable(!detail && !overlay).digitalCrownRotation($crown,from:-100,through:100,by:1,sensitivity:.low,isContinuous:false,isHapticFeedbackEnabled:true)
            .onChange(of:crown){_,new in if !detail && !overlay && abs(new-lastCrown)>=1 {peer(new<lastCrown ? 1:-1);lastCrown=new}}
        }.ignoresSafeArea().preferredColorScheme(.light)
        .task(id:"\(startMillis ?? 0):\(day.count)"){while !Task.isCancelled{try? await Task.sleep(nanoseconds:1_000_000_000);clock=Date()}}
        .onAppear{lastParent=parent}
        .onChange(of:currentId){_,_ in if lastParent==parent && !reduceMotion{turn=orbitStep;withAnimation(.easeOut(duration:0.24)){turn=0}};lastParent=parent}
        .onChange(of:token){_,_ in home()}.onChange(of:busy){_,v in if v{cancel()}}.onChange(of:phase){_,v in if v != .active{cancel()}}.onDisappear{cancel()}
    }
}

private struct ReservationChoices:View {
 let items:[RemoteReservation];let now:Double;let busy:Bool;let find:()->Void;let otherCount:Int;let others:()->Void;let start:(RemoteReservation)->Void
 @State private var selectedId:String?
 private var selected:RemoteReservation?{items.first{$0.id==selectedId}}
 private func time(_ r:RemoteReservation)->String{let f=DateFormatter();f.dateFormat="HH:mm";return f.string(from:Date(timeIntervalSince1970:r.startMillis/1000))+"–"+f.string(from:Date(timeIntervalSince1970:r.endMillis/1000))}
 var body:some View{
  ScrollViewReader{proxy in ScrollView{VStack(spacing:12){
   Text(selected?.title ?? L("예약 선택")).font(.headline).multilineTextAlignment(.center).id("top")
   if let r=selected {
    Text(time(r)).font(.caption)
    if now<r.startMillis{Text(L("예약 예정")).font(.caption)}
    Button(L("시작")){start(r)}.disabled(busy || now<r.startMillis || now>=r.endMillis)
    Button{selectedId=nil}label:{Image(systemName:"chevron.left")}.accessibilityLabel(L("예약 목록")).disabled(busy)
   }else{
    ForEach(items.sorted{($0.startMillis,$0.id)<($1.startMillis,$1.id)}){r in Button{selectedId=r.id}label:{VStack{Text(r.title);Text(time(r)).font(.caption)}}.accessibilityLabel(L("예약: ")+r.title).disabled(busy)}
    Button(action:find){Image(systemName:"magnifyingglass")}.accessibilityLabel(L("찾기")).disabled(busy)
    if otherCount>0{Button(action:others){Text("+\(otherCount)")}.accessibilityLabel(L("함께 진행 {count}",["count":String(otherCount)])).disabled(busy)}
   }
  }.padding(.horizontal,20).padding(.top,8).padding(.bottom,20)}.onChange(of:selected?.id){_,_ in proxy.scrollTo("top",anchor:.top)}}
  .supportViewport().tint(Color(red:23/255,green:54/255,blue:94/255))
 }
}

/// Reserve a fixed clock lane without letting a scrolled button pass underneath it.
private extension View {
    func supportViewport() -> some View {
        GeometryReader { g in
            let height=max(1,g.size.height-44)
            self.frame(width:g.size.width,height:height).clipped()
                .position(x:g.size.width/2,y:44+height/2)
        }.ignoresSafeArea()
    }
}
