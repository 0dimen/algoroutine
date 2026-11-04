package app.algoroutine.wear

import android.graphics.Bitmap
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.io.FileOutputStream
import org.junit.Rule
import org.junit.Test

/** Run each phase as a separate instrumentation invocation, force-stopping between them.
 * Uses the existing disposable demo install; never clears persisted state automatically. */
class PersistenceUiTest {
    @get:Rule val ui = createAndroidComposeRule<MainActivity>()
    private fun expect(text: String) {
        ui.waitUntil(15000) { ui.onAllNodesWithText(text).fetchSemanticsNodes().isNotEmpty() }
        ui.onNodeWithText(text).assertIsDisplayed()
    }
    private fun capture(name: String) {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val file = File(instrumentation.targetContext.filesDir, "$name.png")
        FileOutputStream(file).use { instrumentation.uiAutomation.takeScreenshot().compress(Bitmap.CompressFormat.PNG, 100, it) }
    }
    @Test fun persistenceAcrossProcessRestarts() {
        when (val phase = InstrumentationRegistry.getArguments().getString("phase")) {
            "before" -> {
                expect("문서 열기"); ui.onNodeWithContentDescription("완료").performClick()
                expect("가제 한 줄 적기");  capture("before")
            }
            "after" -> {
                expect("가제 한 줄 적기");  capture("after")
                ui.onNodeWithContentDescription("완료").performClick(); expect("키워드 세 개 적기")
                ui.onNodeWithContentDescription("완료").performClick(); expect("다음 작업 없음")
            }
            "finished" -> {
                expect("다음 작업 없음")
                ui.onNodeWithContentDescription("완료").assertDoesNotExist(); capture("finished")
            }
            else -> error("Specify phase=before, after or finished; got $phase")
        }
    }
}
