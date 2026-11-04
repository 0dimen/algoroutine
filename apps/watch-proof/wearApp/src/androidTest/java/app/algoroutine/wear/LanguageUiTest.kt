package app.algoroutine.wear
import android.content.Intent
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ActivityScenario
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Rule
import org.junit.Test
class LanguageUiTest {
 @get:Rule val ui=createEmptyComposeRule()
 private fun expect(s:String){ui.waitUntil(15000){ui.onAllNodesWithContentDescription(s).fetchSemanticsNodes().isNotEmpty()}}
 @Test fun languageSwitchPersists(){
  val c=InstrumentationRegistry.getInstrumentation().targetContext
  val intent=Intent(c,MainActivity::class.java).putExtra("demo_server",true)
  c.getSharedPreferences("language",0).edit().clear().commit()
  ActivityScenario.launch<MainActivity>(intent).use {
   expect("Find");ui.onNodeWithContentDescription("Find").performClick()
   expect("Enter a request");ui.onNodeWithContentDescription("Enter a request").performClick()
   ui.onNodeWithContentDescription("Language: English",useUnmergedTree=true).performScrollTo().performClick()
   ui.onNodeWithContentDescription("언어: 한국어",useUnmergedTree=true).assertExists()
  }
  ActivityScenario.launch<MainActivity>(intent).use {
   expect("찾기");ui.onNodeWithContentDescription("찾기").performClick()
   expect("검색 입력");ui.onNodeWithContentDescription("검색 입력").performClick()
   ui.onNodeWithContentDescription("언어: 한국어",useUnmergedTree=true).performScrollTo().performClick()
   ui.onNodeWithContentDescription("Language: English",useUnmergedTree=true).assertExists()
  }
 }
}
