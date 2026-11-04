package app.algoroutine.server

import app.algoroutine.core.*
import com.sun.net.httpserver.HttpServer
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.*
import java.net.InetSocketAddress
import java.net.URI
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.nio.file.*
import java.time.Duration
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

private val json=Json{ignoreUnknownKeys=true;encodeDefaults=true}
private class Disk(private val path:Path):ExecutionStorage {
    override fun read():StorageRead = try {StorageRead(Files.readString(path),false)}catch(_:NoSuchFileException){StorageRead(null,false)}catch(_:Exception){StorageRead(null,true)}
    override fun write(content:String):Boolean {
        var temp:Path?=null
        return try {
            Files.createDirectories(path.parent);temp=Files.createTempFile(path.parent,"execution-",".tmp")
            java.nio.channels.FileChannel.open(temp,StandardOpenOption.WRITE).use{c->val b=java.nio.ByteBuffer.wrap(content.toByteArray());while(b.hasRemaining())c.write(b);c.force(true)}
            Files.move(temp,path,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);true
        }catch(_:Exception){false}finally{temp?.let{try{Files.deleteIfExists(it)}catch(_:Exception){}}}
    }
}
private class Service(private val directory:Path,private val library:String,private val demoClock:Boolean=false) {
    private val storage=Disk(directory.resolve("workspace-v2.json"))
    private val scheduleStorage=Disk(directory.resolve("reservations-v1.json"))
    private val clockStorage=Disk(directory.resolve("demo-clock.json"))
    private val rescheduleStorage=Disk(directory.resolve("reschedule-log-v1.json"))
    private val planner=RestRescheduler()
    // Demo clock is opt-in (disposable fixtures only). Normal mode always uses the system clock.
    private var offsetMillis=if(demoClock) clockStorage.read().content?.let{json.parseToJsonElement(it).jsonObject.getValue("offsetMillis").jsonPrimitive.long}?:0L else 0L
    private fun clock()=System.currentTimeMillis()+offsetMillis
    private val client=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build()
    /** Applied plans keyed by idempotency id: [{id, plan, result}]. */
    private fun rescheduleLog():List<JsonObject> {val r=rescheduleStorage.read();check(!r.error){"SCHEDULE_READ_FAILED"};return r.content?.let{json.parseToJsonElement(it).jsonArray.map{e->e.jsonObject}}?:emptyList()}
    private fun schedules():List<Reservation> {val r=scheduleStorage.read();check(!r.error){"SCHEDULE_READ_FAILED"};return r.content?.let{json.decodeFromString<List<Reservation>>(it)}?:emptyList()}
    private data class RestWindow(val occurrenceId:String,val start:Long,val end:Long,val dayEnd:Long)
    private fun startedOccurrences(store:WorkspaceStore)=store.view().runs.map{it.id}.toSet()
    /** The window always starts when the rest routine started (no restart or extension when the preview is reopened). */
    private fun restWindow(store:WorkspaceStore,b:JsonObject):RestWindow {
        val occurrence=b.getValue("occurrenceId").jsonPrimitive.content
        val minutes=b.getValue("restMinutes").jsonPrimitive.int;require(minutes in 1..720)
        val dayEnd=b["dayEnd"]?.jsonPrimitive?.content?:"21:00";require(dayEnd.matches(Regex("([01][0-9]|2[0-3]):[0-5][0-9]")))
        val startedAt=store.events().firstOrNull{it.kind=="start" && it.occurrenceId==occurrence}?.atMillis?:throw IllegalArgumentException("REST_NOT_STARTED")
        val start=startedAt-startedAt%60_000L // whole minutes keep proposed times readable
        val zone=java.time.ZoneId.systemDefault()
        val limit=java.time.Instant.ofEpochMilli(start).atZone(zone).toLocalDate().atTime(java.time.LocalTime.parse(dayEnd)).atZone(zone).toInstant().toEpochMilli()
        return RestWindow(occurrence,start,start+minutes*60_000L,limit)
    }
    private fun engine():WorkspaceStore=WorkspaceStore(storage).also{check(it.error==null){it.error!!}}
    private fun definition(id:String,version:Int):RunDefinition {
        require(id.matches(Regex("[A-Za-z0-9_-]+"))&&version>0)
        val req=HttpRequest.newBuilder(URI.create("$library/api/routine?id=$id&version=$version")).timeout(Duration.ofSeconds(3)).GET().build()
        val response=client.send(req,HttpResponse.BodyHandlers.ofString());check(response.statusCode()==200){"DEFINITION_UNAVAILABLE"}
        val r=json.parseToJsonElement(response.body()).jsonObject
        return RunDefinition(r.getValue("id").jsonPrimitive.content,r.getValue("version").jsonPrimitive.int,r.getValue("title").jsonPrimitive.content,r.getValue("author").jsonObject.getValue("name").jsonPrimitive.content,
            r.getValue("steps").jsonArray.map{val v=it.jsonObject;RoutineStep(v.getValue("id").jsonPrimitive.content,v.getValue("title").jsonPrimitive.content)},description=r["description"]?.jsonPrimitive?.content.orEmpty())
    }
    private fun context(store:WorkspaceStore,now:Long):JsonObject {
        val view=store.view();val done=view.runs.map{it.id}.toSet()
        val all=schedules();val selected=ScheduleSelector().select(all.filter{it.occurrenceId !in done},now,true)
        // "My routine": today's running routines and reservations in time order (read-only, local day).
        val zone=java.time.ZoneId.systemDefault();val today=java.time.Instant.ofEpochMilli(now).atZone(zone).toLocalDate()
        val dayStart=today.atStartOfDay(zone).toInstant().toEpochMilli();val dayEnd=today.plusDays(1).atStartOfDay(zone).toInstant().toEpochMilli()
        val day=DayOrbit.items(view.runs,all,DayOrbit.startTimes(store.events()),now,dayStart,dayEnd)
        // Orbit time scales per depth (shared core OrbitScales) + wall-clock ticks for this instant, so the phone only draws.
        val zoneOffset=zone.rules.getOffset(java.time.Instant.ofEpochMilli(now)).totalSeconds*1000L
        val orbit=buildJsonObject{for(sc in OrbitScales.all) put(sc.depth,buildJsonObject{put("scale",json.encodeToJsonElement(sc));put("ticks",json.encodeToJsonElement(OrbitScales.ticks(sc,now,zoneOffset)))})}
        // The orbit is one clock (shared core OrbitClock): every node at its time, the current item at now with its timer span.
        val events=store.events()
        val clockSlots=buildJsonObject{
            put("day",json.encodeToJsonElement(OrbitClock.day(day,view.runs,events,view.focusId,now)))
            put("runs",buildJsonObject{for(r in view.runs.filter{it.status=="running"}) put(r.id,json.encodeToJsonElement(OrbitClock.steps(r,events,now)))})
        }
        return buildJsonObject{put("workspace",json.encodeToJsonElement(view));put("reservation",json.encodeToJsonElement(selected));put("day",json.encodeToJsonElement(day));put("orbit",orbit);put("clock",clockSlots);put("serverNow",now)}
    }
    @Synchronized fun tick() {
        val store=engine();check(store.reconcile(clock())){store.error?:"EXPIRY_UNCONFIRMED"}
    }
    @Synchronized fun request(path:String,body:String?):JsonElement {
        val now=clock();val store=engine();check(store.reconcile(now)){store.error?:"EXPIRY_UNCONFIRMED"}
        return when(path) {
            "/search" -> {
                val value=json.parseToJsonElement(body?:error("BODY_REQUIRED")).jsonObject.getValue("query").jsonPrimitive
                require(value.isString && value.content.length<=500)
                val req=HttpRequest.newBuilder(URI.create("$library/api/search")).timeout(Duration.ofSeconds(3)).header("Content-Type","application/json").header("X-Routine-App","local").POST(HttpRequest.BodyPublishers.ofString(body)).build()
                val response=client.send(req,HttpResponse.BodyHandlers.ofString());check(response.statusCode()==200){"SEARCH_UNAVAILABLE"}
                json.parseToJsonElement(response.body())
            }
            "/library" -> {
                val req=HttpRequest.newBuilder(URI.create("$library/api/library")).timeout(Duration.ofSeconds(3)).GET().build()
                val response=client.send(req,HttpResponse.BodyHandlers.ofString())
                check(response.statusCode()==200){"LIBRARY_UNAVAILABLE"}
                json.parseToJsonElement(response.body())
            }
            "/context" -> context(store,now)
            "/events" -> json.encodeToJsonElement(store.events())
            "/command" -> {
                var c=json.decodeFromString<RunCommand>(body?:error("BODY_REQUIRED"))
                require(c.kind!="expire" && !c.id.startsWith("system:")){"RESERVED_COMMAND"}
                if(c.kind=="start") {
                    val ref=c.definition?:error("DEFINITION_REQUIRED")
                    val reservation=schedules().firstOrNull{it.occurrenceId==c.occurrenceId}
                    if(reservation!=null) require(ref.id==reservation.definitionId&&ref.version==reservation.definitionVersion)
                    require(reservation!=null || !c.occurrenceId.startsWith("reserved-"))
                    // A plain schedule has no library definition: it starts as a zero-step run with its own title.
                    require(reservation!=null || ref.id!=ReservationKind.PLAIN_SCHEDULE_ID)
                    val saved=store.savedCommand(c.id)
                    val frozen=if(saved?.kind=="start" && saved.definition?.id==ref.id && saved.definition?.version==ref.version) saved.definition!!
                        else if(reservation?.kind==ReservationKind.SCHEDULE) ReservationKind.plainDefinition(reservation) else definition(ref.id,ref.version)
                    c=c.copy(definition=if(reservation==null)frozen else frozen.copy(windowStartMillis=reservation.startMillis,windowEndMillis=reservation.endMillis))
                }
                val appliedAt=clock();check(store.reconcile(appliedAt)){store.error?:"EXPIRY_UNCONFIRMED"}
                val result=store.execute(c,appliedAt)?:error(store.error?:"WRITE_UNCONFIRMED")
                buildJsonObject{put("result",json.encodeToJsonElement(result));put("context",context(store,appliedAt))}
            }
            "/reservations" -> {
                if(body!=null) {
                    val item=json.decodeFromString<Reservation>(body);require(item.id.matches(Regex("[A-Za-z0-9_-]+")))
                    require(item.startMillis<item.endMillis && item.endMillis>now)
                    require(item.kind in setOf(ReservationKind.ROUTINE,ReservationKind.SCHEDULE)){"UNKNOWN_KIND"}
                    // Plain schedule: no definition lookup; the user's title is kept (trimmed, 1..120 chars).
                    val title=if(item.kind==ReservationKind.SCHEDULE) item.title.trim().also{require(it.length in 1..120)} else definition(item.definitionId,item.definitionVersion).title
                    require(item.deadlineMillis.let{it==null||it>=item.endMillis}){"DEADLINE_BEFORE_END"}
                    // Status/history are written only by the reschedule apply path.
                    val items=schedules();val fixed=item.copy(title=title,definitionId=if(item.kind==ReservationKind.SCHEDULE)ReservationKind.PLAIN_SCHEDULE_ID else item.definitionId,definitionVersion=if(item.kind==ReservationKind.SCHEDULE)1 else item.definitionVersion,occurrenceId="reserved-${item.id}",status=null,history=emptyList(),movable=item.movable&&!item.required)
                    val existing=items.firstOrNull{it.id==item.id};require(existing==null||existing==fixed){"RESERVATION_CONFLICT"}
                    if(existing==null)check(scheduleStorage.write(json.encodeToString(items+fixed))){"WRITE_UNCONFIRMED"}
                }
                json.encodeToJsonElement(schedules())
            }
            "/reschedule/preview" -> {
                // Read-only: validates optional AI suggestions and returns the batch proposal; nothing is written.
                val b=json.parseToJsonElement(body?:error("BODY_REQUIRED")).jsonObject;val w=restWindow(store,b)
                val suggestions=b["suggestions"]?.let{json.decodeFromJsonElement<List<RestDecision>>(it)}
                require((suggestions?.size?:0)<=50)
                val items=schedules();val started=startedOccurrences(store)
                val proposal=planner.propose(items,started,w.occurrenceId,w.start,w.end,w.dayEnd,suggestions)
                buildJsonObject{put("proposal",json.encodeToJsonElement(proposal));put("rejected",json.encodeToJsonElement(suggestions?.let{planner.rejectedSuggestions(items,started,w.start,w.end,it)}.orEmpty()));put("serverNow",now)}
            }
            "/reschedule/apply" -> {
                val b=json.parseToJsonElement(body?:error("BODY_REQUIRED")).jsonObject
                val id=b.getValue("id").jsonPrimitive.content;require(id.matches(Regex("[A-Za-z0-9_-]{1,100}")))
                val w=restWindow(store,b);val expected=b.getValue("expectedRevision").jsonPrimitive.content
                val decisions=json.decodeFromJsonElement<List<RestDecision>>(b.getValue("decisions"));require(decisions.size<=50)
                require(decisions.all{it.source in setOf("ai","rule","user")})
                val dryRun=b["dryRun"]?.jsonPrimitive?.boolean==true
                val log=rescheduleLog();val request=buildJsonObject{put("occurrenceId",w.occurrenceId);put("start",w.start);put("end",w.end);put("dayEnd",w.dayEnd);put("expectedRevision",expected);put("decisions",json.encodeToJsonElement(decisions))}
                val previous=log.firstOrNull{it.getValue("id").jsonPrimitive.content==id}
                // Same idempotency key replays its stored result; a different request under the same key is refused.
                if(previous!=null && !dryRun) return if(previous.getValue("request")==request) previous.getValue("result") else json.encodeToJsonElement(RestApplyResult(false,"COMMAND_CONFLICT",reservations=schedules()))
                val items=schedules();val started=startedOccurrences(store);val revision=planner.revision(items)
                val result=when {
                    // A second Apply of the same choices (new key) after the first one succeeded changes nothing.
                    revision!=expected && log.any{it.getValue("request")==request && it.getValue("resultRevision").jsonPrimitive.content==revision} -> RestApplyResult(true,"ALREADY_APPLIED",reservations=items)
                    revision!=expected -> RestApplyResult(false,"STALE_REVISION",reservations=items)
                    else -> {
                        val issues=planner.validate(items,started,w.start,w.end,w.dayEnd,decisions)
                        if(issues.isNotEmpty()) RestApplyResult(false,"INVALID_DECISIONS",issues,items)
                        else if(dryRun) RestApplyResult(true,"VALID",reservations=items)
                        else {val next=planner.apply(items,decisions,id,now);check(scheduleStorage.write(json.encodeToString(next))){"WRITE_UNCONFIRMED"};RestApplyResult(true,"APPLIED",reservations=next)}
                    }
                }
                if(result.reason=="APPLIED") check(rescheduleStorage.write(json.encodeToString(JsonArray(log+buildJsonObject{put("id",id);put("request",request);put("resultRevision",planner.revision(result.reservations));put("result",json.encodeToJsonElement(result))})))){"WRITE_UNCONFIRMED"}
                json.encodeToJsonElement(result)
            }
            "/demo/clock" -> {
                require(demoClock){"NOT_FOUND"}
                if(body!=null) {
                    val b=json.parseToJsonElement(body).jsonObject
                    val target=b["setMillis"]?.jsonPrimitive?.long?:(now+b.getValue("advanceMinutes").jsonPrimitive.long.also{require(it in 1..1440)}*60_000L)
                    require(target>0);val next=target-System.currentTimeMillis()
                    check(clockStorage.write(json.encodeToString(buildJsonObject{put("offsetMillis",next)}))){"WRITE_UNCONFIRMED"};offsetMillis=next
                    val after=engine();check(after.reconcile(clock())){after.error?:"EXPIRY_UNCONFIRMED"}
                }
                buildJsonObject{put("serverNow",clock());put("offsetMillis",offsetMillis)}
            }
            else -> error("NOT_FOUND")
        }
    }
}
fun main(args:Array<String>) {
    val port=args.getOrNull(0)?.toInt()?:8791
    val directory=Path.of(args.getOrNull(1)?:"${System.getProperty("user.home")}/.emotion-scheduler/execution").toAbsolutePath()
    val demoClock=args.getOrNull(3)=="--demo-clock"
    val service=Service(directory,args.getOrNull(2)?:"http://127.0.0.1:8780",demoClock)
    val server=HttpServer.create(InetSocketAddress("127.0.0.1",port),0)
    server.executor=Executors.newFixedThreadPool(2)
    server.createContext("/"){x->
        var status=200
        val response=try {
            require(x.requestHeaders.getFirst("Host") in setOf("127.0.0.1:$port","localhost:$port","10.0.2.2:$port")){"FORBIDDEN_HOST"}
            require(x.requestMethod in setOf("GET","POST")){"METHOD_NOT_ALLOWED"}
            require(x.requestURI.path in setOf("/context","/command","/events","/reservations","/library","/search","/reschedule/preview","/reschedule/apply")+(if(demoClock)setOf("/demo/clock") else emptySet())){"NOT_FOUND"}
            val origin=x.requestHeaders.getFirst("Origin");require(origin==null||origin=="http://127.0.0.1:8780"||origin=="http://localhost:8780"){"FORBIDDEN_ORIGIN"}
            val body=if(x.requestMethod=="POST") {
                require(x.requestHeaders.getFirst("X-Routine-App")=="local"){"FORBIDDEN"}
                val bytes=x.requestBody.readNBytes(150001);require(bytes.size<=150000){"BODY_TOO_LARGE"};bytes.toString(Charsets.UTF_8)
            }else null
            require(x.requestURI.path !in setOf("/command","/reschedule/preview","/reschedule/apply")||body!=null){"BODY_REQUIRED"}
            service.request(x.requestURI.path,body)
        }catch(e:Exception){status=if(e is IllegalArgumentException)400 else 503;buildJsonObject{put("error",buildJsonObject{put("code","REQUEST_FAILED");put("message","요청을 확인하지 못했습니다. 같은 요청의 결과를 다시 확인해 주세요.")})}}
        val bytes=json.encodeToString(response).toByteArray();x.responseHeaders.set("Content-Type","application/json; charset=utf-8");x.responseHeaders.set("Cache-Control","no-store");x.sendResponseHeaders(status,bytes.size.toLong());x.responseBody.use{it.write(bytes)}
    }
    val ticker=Executors.newSingleThreadScheduledExecutor()
    ticker.scheduleWithFixedDelay({try{service.tick()}catch(_:Exception){System.err.println("Expiry persistence unavailable; retrying")}},0,1,TimeUnit.SECONDS)
    Runtime.getRuntime().addShutdownHook(Thread{ticker.shutdownNow();server.stop(0)})
    server.start();println("Local KMP execution service: http://127.0.0.1:$port"+if(demoClock)" (demo clock enabled)" else "")
}
