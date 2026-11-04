package app.algoroutine.wear

import android.app.Activity
import android.content.Intent
import android.content.ActivityNotFoundException
import android.speech.RecognizerIntent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.text.style.TextOverflow
import kotlin.math.abs
import androidx.compose.ui.text.TextStyle
import androidx.compose.foundation.*
import androidx.compose.foundation.gestures.scrollBy
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.*
import androidx.compose.ui.*
import androidx.compose.ui.focus.*
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.input.rotary.onRotaryScrollEvent
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.*
import androidx.compose.ui.graphics.Color
import androidx.wear.compose.material.Text
import app.algoroutine.core.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import kotlinx.serialization.json.*

/** Local library and prepared catalog search. Browsing is read-only; Start uses the durable command path. */
@Composable fun FindRoutineScreen(busy:Boolean,onBack:()->Unit,onStart:(RunDefinition)->Unit){
    var items by remember{mutableStateOf<List<JsonObject>?>(null)}
    var selected by remember{mutableStateOf<JsonObject?>(null)}
    var stepIndex by remember{mutableStateOf<Int?>(null)}
    var error by remember{mutableStateOf(false)}
    var attempt by remember{mutableStateOf(0)}
    var query by remember{mutableStateOf("")}
    var submitted by remember{mutableStateOf("")}
    var page by remember{mutableStateOf(0)}
    var editing by remember{mutableStateOf(false)}
    var voiceNotice by remember{mutableStateOf<String?>(null)}
    val voice=rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()){result->
        if(result.resultCode==Activity.RESULT_OK){val text=result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull();if(!text.isNullOrBlank()){query=text.take(500);voiceNotice=tr("내용을 확인해 주세요")}else voiceNotice=tr("말한 내용을 확인하지 못했어요")}
    }
    val keyboard=LocalSoftwareKeyboardController.current
    LaunchedEffect(attempt){error=false;items=null;page=0;try{items=remoteCall(body=buildJsonObject{put("query",submitted)}.toString(),path="search").getValue("items").jsonArray.map{it.jsonObject}}catch(e:CancellationException){throw e}catch(_:Exception){error=true}}
    val navy=Color(0xFF17365E)
    if(selected==null&&!editing){
        RoutineDeck(items=items,page=page,busy=busy,error=error,query=submitted,
            onPage={page=it},onOpen={selected=it;stepIndex=null},onBack=onBack,onEdit={editing=true},onRetry={attempt++},onStart=onStart)
        return
    }
    val item=selected
    fun submit(){keyboard?.hide();submitted=query.trim();editing=false;attempt++}
    key(item?.get("id"),stepIndex,editing){APage(backLabel=if(item==null)tr("돌아가기") else tr("찾기"),back={keyboard?.hide();if(stepIndex!=null)stepIndex=null else if(item==null)editing=false else selected=null},actionLabel=if(item==null)tr("찾기") else if(busy)tr("시작 중") else tr("시작"),enabled=!busy,action={if(item==null)submit() else onStart(definition(item))},onCurrent=onBack){
        if(item!=null){
            val steps=item.getValue("steps").jsonArray
            val step=stepIndex?.let{steps[it].jsonObject}
            Text((step?:item).getValue("title").jsonPrimitive.content,color=AInk,fontSize=19.sp)
            ASource(source(item))
            if(step==null){
                steps.forEachIndexed{i,s->AStepRow("${i+1}",s.jsonObject.getValue("title").jsonPrimitive.content){stepIndex=i}}
                val copy=item["reason"]?.jsonPrimitive?.content ?: item["description"]?.jsonPrimitive?.content.orEmpty()
                if(copy.isNotBlank())Text(copy,color=ASlate,fontSize=14.sp)
            }else{
                val copy=step["description"]?.jsonPrimitive?.content.orEmpty()
                if(copy.isNotBlank())Text(copy,color=ASlate,fontSize=14.sp)
                AStepRow("‹",item.getValue("title").jsonPrimitive.content){stepIndex=null}
            }
        }else{
            Text(tr("어떤 루틴을 찾으세요?"),color=AInk,fontSize=18.sp)
            FindButton(tr("말하기"),enabled=!busy){try{voice.launch(Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,RecognizerIntent.LANGUAGE_MODEL_FREE_FORM).putExtra(RecognizerIntent.EXTRA_LANGUAGE,AppLanguage.speechTag).putExtra(RecognizerIntent.EXTRA_PROMPT,tr("막막하다면 지금 상황을 말해 주세요")))}catch(_:ActivityNotFoundException){voiceNotice=tr("음성을 사용할 수 없어요. 아래에서 입력해 주세요")}}
            if(voiceNotice!=null)Text(voiceNotice!!,color=ASlate,fontSize=12.sp)
            BasicTextField(value=query,onValueChange={query=it.take(500)},textStyle=TextStyle(color=AInk,fontSize=16.sp),modifier=Modifier.fillMaxWidth().heightIn(min=44.dp).background(ASubtle,RoundedCornerShape(12.dp)).padding(10.dp).semantics{contentDescription=tr("검색 내용")},decorationBox={field->if(query.isEmpty())Text(tr("지금 상황을 적어도 좋아요"),color=ASlate,fontSize=13.sp);field()})
            Text(tr("막막하다면 지금 상황을 말해 주세요"),color=ASlate,fontSize=12.sp)
            AStepRow("◎",tr("언어")+": "+AppLanguage.displayName){AppLanguage.cycle()}
        }
    }}

}
@Composable private fun FindButton(label:String,enabled:Boolean=true,click:()->Unit){Box(Modifier.fillMaxWidth().heightIn(min=44.dp).background(Color(0xFF17365E),RoundedCornerShape(22.dp)).clickable(enabled=enabled,onClick=click).semantics{contentDescription=label;role=Role.Button}.padding(10.dp),contentAlignment=Alignment.Center){Text(label,color=Color.White,fontSize=15.sp)}}

/** Only the foreground card is actionable. Background cards imply vertical continuation. */
@Composable private fun RoutineDeck(items:List<JsonObject>?,page:Int,busy:Boolean,error:Boolean,query:String,
    onPage:(Int)->Unit,onOpen:(JsonObject)->Unit,onBack:()->Unit,onEdit:()->Unit,onRetry:()->Unit,onStart:(RunDefinition)->Unit){
    val focus=remember{FocusRequester()};var rotary by remember{mutableStateOf(0f)}
    val count=items?.size?:0
    fun move(delta:Int){if(count>0)onPage((page+delta).coerceIn(0,count-1))}
    LaunchedEffect(busy){if(!busy)focus.requestFocus()}
    BoxWithConstraints(Modifier.fillMaxSize().background(Color.White).clipToBounds()
        .focusRequester(focus).onRotaryScrollEvent{rotary+=it.verticalScrollPixels;if(abs(rotary)>28){move(if(rotary>0)1 else -1);rotary=0f};true}.focusable()
        .pointerInput(page,count){var drag=0f;detectVerticalDragGestures(onDragStart={drag=0f},onVerticalDrag={change,dy->change.consume();drag+=dy},onDragEnd={if(abs(drag)>30)move(if(drag<0)1 else -1)})}){
        val h=maxHeight;val cardHeight=h*.36f
        AClock()
        ABack(tr("돌아가기"),Modifier.offset(x=24.dp,y=22.dp),onBack)
        Box(Modifier.align(Alignment.TopCenter).offset(y=22.dp).size(64.dp,44.dp).clickable(onClick=onBack).semantics{contentDescription=tr("현재");role=Role.Button},contentAlignment=Alignment.Center){Text(tr("현재"),color=ANavy,fontSize=11.sp)}
        Box(Modifier.align(Alignment.TopEnd).offset(x=(-24).dp,y=22.dp).size(44.dp).clickable(enabled=!busy,onClick=onEdit).semantics{contentDescription=tr("검색 입력");role=Role.Button},contentAlignment=Alignment.Center){Text("⌕",color=ANavy,fontSize=24.sp)}
        if(error||items==null||count==0){Column(Modifier.align(Alignment.Center).padding(horizontal=36.dp),horizontalAlignment=Alignment.CenterHorizontally){
            Text(if(error)tr("연결을 확인해 주세요") else if(items==null)tr("찾는 중") else tr("맞는 루틴이 없어요"),color=ANavy,textAlign=TextAlign.Center)
            if(error)FindButton(tr("다시"),click=onRetry)
            if(count==0&&items!=null&&!error)FindButton(tr("더 자세하게"),click=onEdit)
        }}else{
            val cy=h*.44f+if(page>0)8.dp else 0.dp
            val near=listOf(page-1,page+1,page+2).filter{it in 0 until count}.take(2)
            near.reversed().forEach{index->
                val delta=if(index<page) -1 else index-page
                Box(Modifier.offset(x=40.dp,y=cy-cardHeight/2+if(delta<0)(-14).dp else (12*delta).dp).width(maxWidth-80.dp).height(cardHeight).background(Color(0xFFD5DFEC).copy(alpha=if(delta==2).5f else 1f),RoundedCornerShape(14.dp)).clearAndSetSemantics{},contentAlignment=if(delta<0)Alignment.TopCenter else Alignment.BottomCenter){Text(items[index].getValue("title").jsonPrimitive.content,color=ASlate,fontSize=10.sp,maxLines=1,overflow=TextOverflow.Ellipsis,modifier=Modifier.padding(horizontal=10.dp,vertical=2.dp))}
            }
            val item=items[page.coerceIn(0,count-1)]
            Column(Modifier.offset(x=30.dp,y=cy-cardHeight/2).width(maxWidth-60.dp).height(cardHeight).background(ASubtle,RoundedCornerShape(16.dp))
                .clickable(enabled=!busy){onOpen(item)}.semantics{contentDescription=tr("루틴: {title}", "title" to item.getValue("title").jsonPrimitive.content);role=Role.Button;customActions=listOf(CustomAccessibilityAction(tr("이전 추천")){move(-1);true},CustomAccessibilityAction(tr("다음 추천")){move(1);true})}.padding(horizontal=12.dp,vertical=6.dp),verticalArrangement=Arrangement.spacedBy(3.dp)){
                Text(item.getValue("title").jsonPrimitive.content,color=AInk,fontSize=15.sp,maxLines=2,overflow=TextOverflow.Ellipsis)
                Text(source(item),color=ASlate,fontSize=10.sp,maxLines=1,overflow=TextOverflow.Ellipsis)
                val copy=item["reason"]?.jsonPrimitive?.content ?: item["description"]?.jsonPrimitive?.content.orEmpty()
                if(cardHeight>=78.dp&&copy.isNotBlank())Text(copy,color=ASlate,fontSize=11.sp,maxLines=1,overflow=TextOverflow.Ellipsis)
            }
            AAction(if(busy)tr("시작 중") else tr("시작"),Modifier.align(Alignment.BottomCenter).padding(bottom=16.dp).width(maxWidth*.62f),!busy){onStart(definition(item))}
        }

    }
}

private fun source(item:JsonObject)= (when(item["source"]?.jsonPrimitive?.content){"mine"->tr("내 루틴");"collected"->tr("보관함");else->tr("라이브러리")})+" · "+item.getValue("author").jsonObject.getValue("name").jsonPrimitive.content
private fun definition(item:JsonObject)=RunDefinition(item.getValue("id").jsonPrimitive.content,item.getValue("version").jsonPrimitive.int,item.getValue("title").jsonPrimitive.content,item.getValue("author").jsonObject.getValue("name").jsonPrimitive.content,item.getValue("steps").jsonArray.map{val s=it.jsonObject;RoutineStep(s.getValue("id").jsonPrimitive.content,s.getValue("title").jsonPrimitive.content)})
