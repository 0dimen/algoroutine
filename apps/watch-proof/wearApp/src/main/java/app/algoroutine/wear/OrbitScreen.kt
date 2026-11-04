package app.algoroutine.wear

import androidx.compose.foundation.*
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.drawscope.clipRect
import androidx.compose.foundation.gestures.scrollBy
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.*
import androidx.compose.ui.*
import androidx.compose.ui.draw.blur
import androidx.compose.ui.focus.*
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.*
import androidx.compose.ui.input.rotary.onRotaryScrollEvent
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.*
import androidx.wear.compose.material.Text
import app.algoroutine.core.*
import kotlinx.coroutines.*
import kotlin.math.*

private val ink=Color(0xFF14243D);private val navy=Color(0xFF17365E);private val orange=Color(0xFFF38A20)
private val slate=Color(0xFF4F617A);private val line=Color(0xFF71859E);private val pale=Color(0xFFD5DFEC)

/** Real steps are siblings, never fabricated satellites. Parent view alone exposes child satellites. */
@Composable fun OrbitScreen(parent:String,steps:List<StepView>,currentId:String?,order:List<String>,token:String,busy:Boolean,
    windowStart:Long?=null,windowEnd:Long?=null,now:Long=0,primary:String=tr("완료"),error:String?=null,
    otherCount:Int=0,onOthers:()->Unit={},onFind:(()->Unit)?=null,onAction:(String)->Unit,onRefresh:()->Unit,optionsEnabled:Boolean=true,author:String="",description:String=""){
    val arranged=order.mapNotNull{id->steps.firstOrNull{it.id==id}}.ifEmpty{steps}
    val actual=arranged.indexOfFirst{it.id==currentId}.coerceAtLeast(0)
    var browse by remember(token){mutableStateOf<Int?>(null)};var root by remember(token){mutableStateOf(false)}
    var detail by remember(token){mutableStateOf(false)};var detailStep by remember(token){mutableStateOf<Int?>(null)};var overlay by remember(token){mutableStateOf(false)}
    var selected by remember{mutableStateOf(-1)};var rotary by remember{mutableStateOf(0f)}
    val turn=remember{Animatable(0f)};var orbitStep by remember{mutableStateOf(9f)}
    var lastId by remember{mutableStateOf(currentId)};var lastParent by remember{mutableStateOf(parent)}
    LaunchedEffect(currentId,parent){if(lastId!=null&&currentId!=lastId&&parent==lastParent){turn.snapTo(orbitStep);turn.animateTo(0f,tween(240))};lastId=currentId;lastParent=parent}
    val focus=remember{FocusRequester()};val geometry=remember{WatchGeometry()}
    val shown=(browse?:actual).coerceIn(0,max(0,arranged.lastIndex));val item=arranged.getOrNull(shown)
    val isBrowsing=browse!=null;val title=if(root||item==null)parent else item.title
    val view=LocalView.current
    var contactEpoch by remember{mutableStateOf(0)}
    DisposableEffect(view){val observer=android.view.ViewTreeObserver.OnWindowFocusChangeListener{focused->if(!focused){contactEpoch++;overlay=false;selected=-1}};view.viewTreeObserver.addOnWindowFocusChangeListener(observer);onDispose{view.viewTreeObserver.removeOnWindowFocusChangeListener(observer)}}
    val density=LocalDensity.current.density
    val round=LocalConfiguration.current.isScreenRound
    fun home(){browse=null;root=false;detail=false;overlay=false}
    fun peer(direction:Int){if(!root&&arranged.isNotEmpty()){browse=(shown+direction).coerceIn(0,arranged.lastIndex).takeUnless{it==actual}}}
    fun perform(index:Int){overlay=false;selected=-1;if(index==0)onAction(if(root)"completeParent" else "complete")else if(!root)onAction(if(index==1)"defer" else "skip")}
    LaunchedEffect(detail,overlay,busy){if(!detail&&!overlay&&!busy)focus.requestFocus()}
    BoxWithConstraints(Modifier.fillMaxSize().background(Color.White)){
        val w=maxWidth.value;val h=maxHeight.value;SideEffect{orbitStep=geometry.peerAngle(w.toDouble()).toFloat()};val footerY=h*.78f;val buttonWidth=min(min(132f,w-64),2*sqrt(max(0f,(w/2-4)*(w/2-4)-(footerY+22-h/2)*(footerY+22-h/2))))
        val ctaX=w/2
        val ctaWidth=buttonWidth
        val titleWidth=min(w-56,2*sqrt(max(0f,(w/2-8)*(w/2-8)-(h*.13f+4-h/2)*(h*.13f+4-h/2))))
        if(detail){
            key(detailStep){APage(backLabel=tr("돌아가기"),back={if(detailStep!=null)detailStep=null else home()},actionLabel=tr("현재"),enabled=!busy,action={home()}){
                Text(detailStep?.let{arranged[it].title} ?: parent,color=AInk,fontSize=19.sp)
                if(author.isNotBlank())ASource(author)
                val index=detailStep
                if(index!=null){
                    if(arranged[index].status=="completed")ASource(tr("완료"))
                    if(arranged[index].status=="skipped")ASource(tr("건너뜀"))
                    if(arranged[index].status=="elapsed")ASource(tr("시간 경과"))
                    AStepRow("‹",parent){detailStep=null}
                }else{
                    arranged.forEachIndexed{i,n->AStepRow(if(n.status=="completed")"✓" else if(n.status=="skipped")"↦" else if(n.status=="elapsed")"◷" else "${i+1}",n.title){detailStep=i}}
                    if(description.isNotBlank())Text(description,color=ASlate,fontSize=14.sp)
                    if(windowStart!=null&&windowEnd!=null)Text(orbitTimes(windowStart,windowEnd),color=ASlate,fontSize=12.sp)
                }
            }}

        }else{
            Box(Modifier.fillMaxSize().blur(if(overlay)6.dp else 0.dp).then(if(overlay)Modifier.clearAndSetSemantics{} else Modifier)
                .focusRequester(focus).onRotaryScrollEvent{if(!overlay&&!busy){rotary+=it.verticalScrollPixels;if(abs(rotary)>28){peer(if(rotary>0)1 else -1);rotary=0f};true}else false}.focusable()
                .pointerInput(token,busy,root,browse,contactEpoch){
                    coroutineScope{awaitEachGesture{
                        val down=awaitFirstDown(requireUnconsumed=false);if(busy)return@awaitEachGesture
                        val x=down.position.x/density;val y=down.position.y/density
                        val wasOverlay=overlay;val cta=abs(y-footerY)<24&&abs(x-ctaX)<ctaWidth/2
                        val planet=abs(x-w/2)<24&&abs(y-h/2)<24
                        val hold=WatchHold();hold.begin(token,0.0,x.toDouble(),y.toDouble())
                        var held=false;var moved=false;var last=down.position
                        val timer=launch{delay(450);if(cta&&!isBrowsing&&primary==tr("완료")&&optionsEnabled&&hold.activate(450.0)){held=true;overlay=true;selected=-1;view.performHapticFeedback(android.view.HapticFeedbackConstants.LONG_PRESS)}}
                        try{
                            var pressed=true
                            while(pressed){val event=awaitPointerEvent();val change=event.changes.firstOrNull{it.id==down.id}?:break;last=change.position
                                val px=last.x/density;val py=last.y/density
                                if(hypot(px-x,py-y)>12)moved=true
                                hold.move(px.toDouble(),py.toDouble())
                                if(held)selected=geometry.option(w.toDouble(),h.toDouble(),px.toDouble(),py.toDouble()).let{if(root&&it>0)-1 else it}
                                pressed=change.pressed
                                if(held||moved)change.consume()
                            }
                            timer.cancel()
                            val dx=last.x/density-x;val dy=last.y/density-y
                            if(held){val choice=hold.finish(token,selected);overlay=false;selected=-1;if(choice>=0)perform(choice)}
                            else if(wasOverlay){val choice=geometry.option(w.toDouble(),h.toDouble(),(last.x/density).toDouble(),(last.y/density).toDouble());overlay=false;if(choice>=0&&(!root||choice==0))perform(choice)}
                            else if(cta&&!moved){if(isBrowsing||(root&&!optionsEnabled))home()else onAction(if(root)"completeParent" else if(primary==tr("시작"))"start" else "complete")}
                            else if(planet&&!moved&&optionsEnabled&&!isBrowsing){overlay=true}
                            else if(max(abs(dx),abs(dy))>35){if(abs(dy)>abs(dx))peer(if(dy<0)1 else -1)else if(dx>0)root=true else root=false}
                        }finally{timer.cancel();hold.cancel();if(held){overlay=false;selected=-1}}
                    }}
                }){
                Canvas(Modifier.fillMaxSize()){
                    val ww=size.width;val hh=size.height;val radius=ww/2;val cy=hh/2
                    clipRect(top=(if(h<215)65 else 81).dp.toPx(),bottom=(footerY-24).dp.toPx()){rotate(if(root)0f else turn.value,pivot=Offset(0f,cy)){
                    if(!root&&item!=null){
                        drawCircle(ASubtle,22.dp.toPx(),Offset(0f,cy));drawCircle(pale,22.dp.toPx(),Offset(0f,cy),style=Stroke(1.dp.toPx()))
                        drawArc(line,(-2*orbitStep-2),4*orbitStep+4,false,Offset(-radius,cy-radius),androidx.compose.ui.geometry.Size(ww,ww),style=Stroke(1.5.dp.toPx()))
                        for(offset in listOf(-2,-1,1,2)){val neighbor=arranged.getOrNull(shown+offset)?:continue;if(!geometry.peerVisible(w.toDouble(),h.toDouble(),offset,isBrowsing))continue;val a=offset*geometry.peerAngle(w.toDouble());val p=Offset(geometry.x(ww.toDouble(),a).toFloat(),geometry.y(ww.toDouble(),hh.toDouble(),a).toFloat());drawCircle(if(neighbor.status=="completed")navy else pale,7.dp.toPx(),p);drawCircle(slate,7.dp.toPx(),p,style=Stroke(1.dp.toPx()));if(neighbor.status=="completed"){drawLine(Color.White,p+Offset(-3f,0f),p+Offset(-.5f,2.5f),1.5.dp.toPx());drawLine(Color.White,p+Offset(-.5f,2.5f),p+Offset(4f,-3f),1.5.dp.toPx())}}
                    }
                    // A parent's reservation is not copied to an untimed child.
                    }}
                    if((root||primary==tr("시작"))&&windowStart!=null&&windowEnd!=null&&windowEnd>windowStart){
                        val progress=((now-windowStart).toDouble()/(windowEnd-windowStart)).coerceIn(0.0,1.0)
                        val a=geometry.arcStart(progress).toFloat();val b=geometry.arcEnd(progress).toFloat()
                        drawArc(pale,a,-a,false,Offset(-radius,cy-radius),androidx.compose.ui.geometry.Size(ww,ww),style=Stroke(6.dp.toPx()))
                        drawArc(slate,0f,b,false,Offset(-radius,cy-radius),androidx.compose.ui.geometry.Size(ww,ww),style=Stroke(6.dp.toPx()))
                        for(v in listOf(a,b)){val angle=v*PI/180;val p=Offset(radius*cos(angle).toFloat(),cy+radius*sin(angle).toFloat());val d=Offset(4.dp.toPx()*cos(angle).toFloat(),4.dp.toPx()*sin(angle).toFloat());drawLine(ink,p-d,p+d,1.dp.toPx())}
                    }
                    run{if(item!=null||root||primary==tr("시작")){drawCircle(Color.White,12.dp.toPx(),Offset(ww/2,cy));drawCircle(orange,9.dp.toPx(),Offset(ww/2,cy));drawCircle(Color(0xFF8C4D00),12.dp.toPx(),Offset(ww/2,cy),style=Stroke(1.dp.toPx()))}
                    }
                    if(root&&arranged.isNotEmpty()){drawCircle(pale,32.dp.toPx(),Offset(ww/2,cy),style=Stroke(1.dp.toPx()));arranged.take(3).forEachIndexed{i,s->val a=(-160+i*160)*PI/180;drawCircle(if(s.status=="completed")navy else pale,3.dp.toPx(),Offset(ww/2+32.dp.toPx()*cos(a).toFloat(),cy+32.dp.toPx()*sin(a).toFloat()))}}
                }
                androidx.wear.compose.material.TimeText(timeSource=androidx.wear.compose.material.TimeTextDefaults.timeSource(androidx.wear.compose.material.TimeTextDefaults.TimeFormat24Hours),timeTextStyle=androidx.wear.compose.material.TimeTextDefaults.timeTextStyle(color=slate))
                Text(title,color=ink,fontSize=17.sp,fontWeight=androidx.compose.ui.text.font.FontWeight.SemiBold,maxLines=if(h<215)1 else 2,overflow=TextOverflow.Ellipsis,textAlign=TextAlign.Start,modifier=Modifier.align(Alignment.TopCenter).padding(top=if(round)54.dp else if(h<215)40.dp else 38.dp).width(titleWidth.dp).height(if(h<215)24.dp else 42.dp).clickable{detailStep=if(root||item==null)null else shown;detail=true}.semantics{contentDescription=tr("상세: {title}", "title" to title)})
                Text(if(isBrowsing)tr("탐색 중") else if((root||primary==tr("시작"))&&windowStart!=null&&windowEnd!=null)orbitTimes(windowStart,windowEnd) else if(primary==tr("시작"))tr("시작 전") else if(!root)"${shown+1} / ${arranged.size}" else "",color=slate,fontSize=11.sp,modifier=Modifier.align(if(root||primary==tr("시작"))Alignment.TopCenter else Alignment.TopStart).padding(start=if(root||primary==tr("시작"))0.dp else 18.dp,top=(h*.78f-41).dp))
                if(!root&&item!=null)Text(parent,color=slate,fontSize=11.sp,maxLines=2,overflow=TextOverflow.Ellipsis,modifier=Modifier.offset(12.dp,(h/2-12).dp).width((w/2-34).dp).height(24.dp).clickable{root=true}.semantics{contentDescription=tr("상위: {title}", "title" to parent)})
                if(otherCount>0)Text("+$otherCount",color=navy,fontSize=12.sp,modifier=Modifier.align(Alignment.CenterEnd).size(44.dp).wrapContentSize().clickable(onClick=onOthers).semantics{contentDescription=tr("함께 진행 {count}", "count" to otherCount)})
                if(onFind!=null)Box(Modifier.offset(if(round)(w*.30f-22).dp else 8.dp,if(round)8.dp else 12.dp).size(44.dp).clickable(enabled=!busy,onClick=onFind).semantics{contentDescription=tr("찾기");role=Role.Button},contentAlignment=Alignment.Center){Canvas(Modifier.size(22.dp)){drawCircle(navy,6.dp.toPx(),Offset(9.dp.toPx(),9.dp.toPx()),style=Stroke(2.dp.toPx()));drawLine(navy,Offset(14.dp.toPx(),14.dp.toPx()),Offset(20.dp.toPx(),20.dp.toPx()),2.dp.toPx())}}
                val label=if(isBrowsing||(root&&!optionsEnabled))tr("현재") else primary
                Box(Modifier.offset((ctaX-ctaWidth/2).dp,(footerY-22).dp).size(ctaWidth.dp,44.dp).background(if(busy)pale else navy,RoundedCornerShape(22.dp)).semantics{contentDescription=label;role=Role.Button;if(optionsEnabled&&!isBrowsing)onLongClick(label=tr("작업 옵션")){overlay=true;true};onClick{if(!busy){if(isBrowsing||(root&&!optionsEnabled))home()else onAction(if(root)"completeParent" else if(primary==tr("시작"))"start" else "complete")};true}},contentAlignment=Alignment.Center){Text(if(busy)tr("저장 중") else if(label==tr("완료"))tr("✓ 완료") else label,color=Color.White,fontSize=16.sp)}
            }
            if(overlay){
                // Same canvas retains the original touch until release; no modal card.
                Text(if(selected>=0)listOf(tr("완료"),tr("미루기"),tr("건너뛰기"))[selected] else "",color=ink,fontSize=16.sp,modifier=Modifier.align(Alignment.TopCenter).padding(top=(h*.19f).dp).semantics{liveRegion=LiveRegionMode.Polite;customActions=listOf(CustomAccessibilityAction(tr("돌아가기")){overlay=false;true})})
                for(i in 0..2)Box(Modifier.offset((w/2+(i-1)*52-22).dp,(h*.38f-22).dp).size(44.dp).background(if(selected==i)navy else Color.White,CircleShape).border(1.dp,slate,CircleShape).semantics{contentDescription=listOf(tr("완료"),tr("미루기"),tr("건너뛰기"))[i];role=Role.Button;onClick{if(!busy&&(!root||i==0))perform(i);true}},contentAlignment=Alignment.Center){AOptionIcon(i,if(selected==i)Color.White else ink)}
            }
        }
        if(error!=null)OrbitButton(tr("결과 확인"),Modifier.align(Alignment.BottomCenter)){onRefresh()}
    }
}
@Composable private fun OrbitButton(label:String,modifier:Modifier=Modifier,onClick:()->Unit){Box(modifier.heightIn(min=44.dp).background(navy,RoundedCornerShape(22.dp)).clickable(onClick=onClick).padding(10.dp),contentAlignment=Alignment.Center){Text(label,color=Color.White,fontSize=15.sp)}}
fun orbitTimes(start:Long,end:Long):String {val f=java.text.SimpleDateFormat("HH:mm",java.util.Locale.KOREA);return f.format(java.util.Date(start))+"–"+f.format(java.util.Date(end))}

@Composable private fun AOptionIcon(index:Int,color:Color){Canvas(Modifier.size(22.dp)){
 val u=size.width/24f
 fun line(x:Float,y:Float,a:Float,b:Float)=drawLine(color,Offset(x*u,y*u),Offset(a*u,b*u),1.8.dp.toPx(),cap=androidx.compose.ui.graphics.StrokeCap.Round)
 when(index){
  0->{line(4f,12f,10f,18f);line(10f,18f,20f,6f)}
  1->{drawArc(color,180f,270f,false,Offset(5*u,5*u),androidx.compose.ui.geometry.Size(14*u,14*u),style=Stroke(1.8.dp.toPx()));line(5f,5f,5f,11f);line(5f,11f,11f,11f)}
  else->{line(5f,5f,14f,12f);line(14f,12f,5f,19f);line(18f,5f,18f,19f)}
 }
}}
