package app.algoroutine.core
import kotlin.math.*

/** Coordinates use the whole app viewport, including reserved system-safe space. */
class WatchGeometry {
    fun x(width:Double,angleDegrees:Double)=width/2*cos(angleDegrees*PI/180)
    fun y(width:Double,height:Double,angleDegrees:Double)=height/2+width/2*sin(angleDegrees*PI/180)
    /** Visible 14-unit neighbors, with a clear gap from the 24-unit current ring. */
    fun peerAngle(width:Double)=2*asin((23.0/width.coerceAtLeast(23.0)).coerceIn(0.0,1.0))*180/PI
    fun peerVisible(width:Double,height:Double,offset:Int,subtitle:Boolean):Boolean {
        if(offset==0 || abs(offset)>2)return false
        val cy=y(width,height,offset*peerAngle(width))
        val titleBottom=if(height<215)64.0 else 80.0
        return cy-7>=titleBottom+1 && cy+7<=height*.78-23
    }
    fun arcStart(progress:Double)=-progress.coerceIn(0.0,1.0)*24
    fun arcEnd(progress:Double)=(1-progress.coerceIn(0.0,1.0))*24
    /** Row has 44-unit targets and 8-unit gaps. Outside all targets is cancellation. */
    fun option(width:Double,height:Double,x:Double,y:Double):Int {
        if(abs(y-height*0.38)>22)return -1
        for(i in 0..2)if(abs(x-(width/2+(i-1)*52))<=22)return i
        return -1
    }
}
/** A hold owns its original action target. Lifting without sliding never selects. */
class WatchHold {
    private var token:String?=null
    private var began=0.0
    private var x=0.0;private var y=0.0
    private var activated=false
    private var moved=false
    fun begin(target:String,at:Double,startX:Double,startY:Double){token=target;began=at;x=startX;y=startY;activated=false;moved=false}
    fun activate(at:Double):Boolean {if(token==null||at-began<450)return false;activated=true;return true}
    fun move(px:Double,py:Double){if(hypot(px-x,py-y)>12){if(!activated)cancel() else moved=true}}
    fun finish(target:String,option:Int):Int {val result=if(token==target&&activated&&moved&&option in 0..2)option else -1;cancel();return result}
    fun cancel(){token=null;activated=false;moved=false}
}
