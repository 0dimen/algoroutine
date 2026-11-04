package app.algoroutine.core
import kotlin.test.*
class WatchInteractionTest {
 @Test fun smallFacesKeepPeerGapAndSafeAreas(){
  val g=WatchGeometry()
  for((w,h) in listOf(162.0 to 197.0,184.0 to 224.0,192.0 to 192.0,208.0 to 248.0,227.0 to 227.0)){
   val distance=w*kotlin.math.sin(g.peerAngle(w)*kotlin.math.PI/360)
   assertTrue(distance>=23.0-.0001,"peer overlaps focus at $w")
   for(subtitle in listOf(false,true))for(offset in listOf(-2,-1,1,2))if(g.peerVisible(w,h,offset,subtitle)){
    val y=g.y(w,h,offset*g.peerAngle(w));assertTrue(y-7>=(if(h<215)64.0 else 80.0)+1);assertTrue(y+7<=h*.78-23)
   }
  }
  for((w,h) in listOf(162.0 to 197.0,184.0 to 224.0,192.0 to 192.0,208.0 to 248.0,227.0 to 227.0)){assertTrue(g.peerVisible(w,h,-1,false),"Previous step must remain visible at $w x $h");assertTrue(g.peerVisible(w,h,1,false),"Next step must remain visible at $w x $h")}
 }
 @Test fun focusAndParentUseCircularCoordinates(){val g=WatchGeometry();for(w in listOf(192.0,208.0,227.0,240.0)){assertEquals(w/2,g.x(w,0.0),.001);assertEquals(140.0,g.y(w,280.0,0.0),.001);assertTrue(g.y(w,280.0,-24.0)<140);assertTrue(g.y(w,280.0,24.0)>140)}}
 @Test fun startMiddleEndKeepFocusFixed(){val g=WatchGeometry();assertEquals(0.0,g.arcStart(0.0),.001);assertEquals(-12.0,g.arcStart(.5));assertEquals(0.0,g.arcEnd(1.0))}
 @Test fun roundTargetsAreInsideMask(){for(w in listOf(192.0,208.0,227.0)){val r=w/2;for(i in -1..1)for(dx in listOf(-22,22))for(dy in listOf(-22,22)){val x=i*52.0+dx;val y=w*.38+dy-r;assertTrue(x*x+y*y<r*r)}}}
 @Test fun rowGapsAndOutsideCancel(){val g=WatchGeometry();assertEquals(0,g.option(208.0,250.0,52.0,95.0));assertEquals(-1,g.option(208.0,250.0,78.0,95.0));assertEquals(-1,g.option(208.0,250.0,104.0,180.0))}
 @Test fun releasingWithoutSlideCancels(){val h=WatchHold();h.begin("a",0.0,100.0,200.0);assertTrue(h.activate(450.0));assertEquals(-1,h.finish("a",0))}
 @Test fun slideSelectsOnlyOriginalTarget(){val h=WatchHold();h.begin("a",0.0,100.0,200.0);h.activate(450.0);h.move(52.0,95.0);assertEquals(-1,h.finish("b",0));h.begin("a",0.0,100.0,200.0);h.activate(450.0);h.move(52.0,95.0);assertEquals(1,h.finish("a",1));assertEquals(-1,h.finish("a",1))}
 @Test fun earlyMotionIsNotCompletion(){val h=WatchHold();h.begin("a",0.0,100.0,200.0);h.move(120.0,200.0);assertFalse(h.activate(450.0));assertEquals(-1,h.finish("a",0))}
}
