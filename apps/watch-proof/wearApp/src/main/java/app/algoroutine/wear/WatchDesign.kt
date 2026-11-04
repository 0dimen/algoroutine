package app.algoroutine.wear

import androidx.compose.foundation.*
import androidx.compose.foundation.gestures.scrollBy
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.*
import androidx.compose.ui.*
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.focus.*
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.rotary.onRotaryScrollEvent
import androidx.compose.ui.semantics.*
import androidx.compose.ui.unit.*
import androidx.wear.compose.material.Text
import kotlinx.coroutines.launch

internal val AInk=Color(0xFF14243D)
internal val ANavy=Color(0xFF17365E)
internal val ASubtle=Color(0xFFF2F5F9)
internal val ASlate=Color(0xFF4F617A)
@Composable internal fun AClock(){androidx.wear.compose.material.TimeText(timeSource=androidx.wear.compose.material.TimeTextDefaults.timeSource(androidx.wear.compose.material.TimeTextDefaults.TimeFormat24Hours),timeTextStyle=androidx.wear.compose.material.TimeTextDefaults.timeTextStyle(color=ASlate))}
@Composable internal fun AAction(label:String,modifier:Modifier=Modifier,enabled:Boolean=true,action:()->Unit){
 Box(modifier.height(44.dp).background(ANavy,RoundedCornerShape(22.dp)).clickable(enabled=enabled,onClick=action).semantics{contentDescription=label;role=Role.Button}.padding(horizontal=8.dp),contentAlignment=Alignment.Center){Text(label,color=Color.White,fontSize=15.sp)}
}
@Composable internal fun ABack(label:String,modifier:Modifier=Modifier,action:()->Unit){Box(modifier.size(44.dp).clickable(onClick=action).semantics{contentDescription=label;role=Role.Button},contentAlignment=Alignment.Center){Text("‹",color=ANavy,fontSize=26.sp)}}
/** Content is clipped below system chrome; the main action never scrolls away. */
@Composable internal fun APage(backLabel:String,back:()->Unit,actionLabel:String,enabled:Boolean=true,action:()->Unit,onCurrent:(()->Unit)?=null,content:@Composable ColumnScope.()->Unit){
 val scroll=rememberScrollState();val focus=remember{FocusRequester()};val scope=rememberCoroutineScope()
 LaunchedEffect(Unit){focus.requestFocus()}
 BoxWithConstraints(Modifier.fillMaxSize().background(Color.White)){
  val h=maxHeight;val inset=if(maxWidth<=200.dp)24.dp else 32.dp
  Column(Modifier.offset(y=58.dp).fillMaxWidth().height((h-122.dp).coerceAtLeast(48.dp)).padding(horizontal=inset).clipToBounds().focusRequester(focus).onRotaryScrollEvent{scope.launch{scroll.scrollBy(it.verticalScrollPixels)};true}.focusable().verticalScroll(scroll),verticalArrangement=Arrangement.spacedBy(8.dp),content=content)
  ABack(backLabel,Modifier.offset(x=inset-8.dp,y=22.dp),back)
  if(onCurrent!=null)Box(Modifier.align(Alignment.TopCenter).offset(y=22.dp).size(64.dp,44.dp).clickable(onClick=onCurrent).semantics{contentDescription=tr("현재");role=Role.Button},contentAlignment=Alignment.Center){Text(tr("현재"),color=ANavy,fontSize=11.sp)}
  AAction(actionLabel,Modifier.align(Alignment.BottomCenter).padding(bottom=16.dp).width(maxWidth*.62f),enabled,action)
  AClock()
 }
}
@Composable internal fun AStepRow(number:String,title:String,action:()->Unit){
 Row(Modifier.fillMaxWidth().heightIn(min=44.dp).background(ASubtle,RoundedCornerShape(12.dp)).clickable(onClick=action).semantics{contentDescription=title;role=Role.Button}.padding(10.dp),horizontalArrangement=Arrangement.spacedBy(8.dp)){
  Text(number,color=ANavy,fontSize=13.sp);Text(title,color=AInk,fontSize=14.sp)
 }
}
@Composable internal fun ASource(text:String){Text(text,color=ASlate,fontSize=11.sp,modifier=Modifier.background(ASubtle,RoundedCornerShape(8.dp)).padding(horizontal=8.dp,vertical=4.dp))}
