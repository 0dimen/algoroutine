package app.algoroutine.wear

import androidx.compose.foundation.*
import androidx.compose.foundation.gestures.scrollBy
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.*
import androidx.compose.ui.*
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.focus.*
import androidx.compose.ui.input.rotary.onRotaryScrollEvent
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.*
import androidx.wear.compose.material.Text
import app.algoroutine.core.Reservation
import kotlinx.coroutines.launch

/** Selection is local preview only. Only explicit Start creates an occurrence. */
@Composable fun ReservationChoices(items:List<Reservation>,now:Long,busy:Boolean,onFind:()->Unit,otherCount:Int=0,onOthers:()->Unit={},onStart:(Reservation)->Unit){
    var selectedId by remember{mutableStateOf<String?>(null)}
    val selected=items.firstOrNull{it.id==selectedId}
    val scroll=rememberScrollState();val scope=rememberCoroutineScope();val focus=remember{FocusRequester()}
    LaunchedEffect(selected?.id){scroll.scrollTo(0)}
    LaunchedEffect(busy){if(!busy)focus.requestFocus()}
    Column(Modifier.fillMaxSize().background(Color.White).focusRequester(focus).onRotaryScrollEvent{if(!busy)scope.launch{scroll.scrollBy(it.verticalScrollPixels)};true}.focusable().padding(vertical=30.dp).verticalScroll(scroll).padding(horizontal=34.dp),horizontalAlignment=Alignment.CenterHorizontally,verticalArrangement=Arrangement.spacedBy(10.dp)){
        Text(if(selected==null)tr("예약 선택") else selected.title,color=Color(0xFF14243D),fontSize=18.sp,textAlign=TextAlign.Center)
        if(selected==null){
            items.sortedWith(compareBy<Reservation>{it.startMillis}.thenBy{it.id}).forEach{r->
                ReservationButton(r.title+"\n"+orbitTimes(r.startMillis,r.endMillis),tr("예약: {title}", "title" to r.title),!busy){selectedId=r.id}
            }
            ReservationButton("⌕",tr("찾기"),!busy,onFind)
            if(otherCount>0)ReservationButton("+$otherCount",tr("함께 진행 {count}", "count" to otherCount),!busy,onOthers)
        }else{
            Text(orbitTimes(selected.startMillis,selected.endMillis),color=Color(0xFF4F617A),fontSize=13.sp)
            if(now<selected.startMillis)Text(tr("예약 예정"),color=Color(0xFF4F617A),fontSize=13.sp)
            ReservationButton(tr("시작"),tr("시작"),!busy&&now>=selected.startMillis&&now<selected.endMillis){onStart(selected)}
            ReservationButton("‹",tr("예약 목록"),!busy){selectedId=null}
        }
    }
}
@Composable private fun ReservationButton(text:String,label:String,enabled:Boolean,click:()->Unit){
    Box(Modifier.fillMaxWidth().heightIn(min=44.dp).background(Color(0xFF17365E).copy(alpha=if(enabled)1f else .4f),RoundedCornerShape(18.dp)).clickable(enabled=enabled,onClick=click).semantics{contentDescription=label;role=Role.Button}.padding(10.dp),contentAlignment=Alignment.Center){Text(text,color=Color.White,fontSize=14.sp,textAlign=TextAlign.Center)}
}

/** Shared safe inset and full-width actions for small round support screens. */
@Composable fun SupportPage(title:String,enabled:Boolean=true,content:@Composable ColumnScope.()->Unit){
    val scroll=rememberScrollState();val scope=rememberCoroutineScope();val focus=remember{FocusRequester()}
    LaunchedEffect(enabled){if(enabled)focus.requestFocus()}
    Column(Modifier.fillMaxSize().focusRequester(focus).onRotaryScrollEvent{if(enabled)scope.launch{scroll.scrollBy(it.verticalScrollPixels)};true}.focusable().verticalScroll(scroll).padding(horizontal=34.dp,vertical=36.dp),horizontalAlignment=Alignment.CenterHorizontally,verticalArrangement=Arrangement.spacedBy(10.dp)){
        Text(title,fontSize=17.sp,textAlign=TextAlign.Center)
        content()
    }
}
@Composable fun SupportButton(text:String,label:String,enabled:Boolean=true,click:()->Unit)=ReservationButton(text,label,enabled,click)
