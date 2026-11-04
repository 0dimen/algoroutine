require 'xcodeproj'
project = Xcodeproj::Project.new(File.join(__dir__, 'RoutineWatch.xcodeproj'))
target = project.new_target(:application, 'RoutineWatch', :watchos, '10.0')
file = project.main_group.new_file('RoutineWatchApp.swift')
target.source_build_phase.add_file_reference(file)
target.source_build_phase.add_file_reference(project.main_group.new_file('AppLanguage.swift'))
target.source_build_phase.add_file_reference(project.main_group.new_file('DeviceConnection.swift'))
target.build_configurations.each do |c|
 s = c.build_settings
 s['PRODUCT_BUNDLE_IDENTIFIER'] = 'app.algoroutine.watchproof'
 s['PRODUCT_NAME'] = 'RoutineWatch'
 s['SWIFT_VERSION'] = '5.0'
 s['GENERATE_INFOPLIST_FILE'] = 'YES'
 s['INFOPLIST_KEY_WKApplication'] = 'YES'
 s['INFOPLIST_KEY_WKWatchOnly'] = 'YES'
 s['INFOPLIST_KEY_CFBundleDisplayName'] = 'RoutineProof'
 s['TARGETED_DEVICE_FAMILY'] = '4'
 s['SUPPORTED_PLATFORMS'] = 'watchos watchsimulator'
 s['CODE_SIGNING_ALLOWED'] = 'NO'
 s['FRAMEWORK_SEARCH_PATHS[sdk=watchsimulator*][arch=x86_64]'] = '$(SRCROOT)/../shared/build/bin/watchosX64/debugFramework'
 s['FRAMEWORK_SEARCH_PATHS[sdk=watchsimulator*][arch=arm64]'] = '$(SRCROOT)/../shared/build/bin/watchosSimulatorArm64/debugFramework'
 s['FRAMEWORK_SEARCH_PATHS[sdk=watchos*][arch=arm64_32]'] = '$(SRCROOT)/../shared/build/bin/watchosArm64/debugFramework'
 s['FRAMEWORK_SEARCH_PATHS[sdk=watchos*][arch=arm64]'] = '$(SRCROOT)/../shared/build/bin/watchosDeviceArm64/debugFramework'
 s['OTHER_LDFLAGS'] = '$(inherited) -framework RoutineCore -lc++'
 s['INFOPLIST_FILE'] = 'Info.Debug.plist' if c.name == 'Debug'
 s['ENABLE_USER_SCRIPT_SANDBOXING'] = 'YES'
end
tests = project.new_target(:ui_test_bundle, 'RoutineWatchUITests', :watchos, '10.0')
tests.source_build_phase.add_file_reference(project.main_group.new_file('RoutineWatchUITests.swift'))
tests.add_dependency(target)
tests.build_configurations.each do |c|
 c.build_settings.merge!({'PRODUCT_BUNDLE_IDENTIFIER'=>'app.algoroutine.watchproof.uitests', 'SWIFT_VERSION'=>'5.0', 'GENERATE_INFOPLIST_FILE'=>'YES', 'CODE_SIGNING_ALLOWED'=>'NO', 'TEST_TARGET_NAME'=>'RoutineWatch', 'TARGETED_DEVICE_FAMILY'=>'4'})
end
project.save
scheme = Xcodeproj::XCScheme.new
scheme.add_build_target(target)
scheme.set_launch_target(target)
scheme.add_test_target(tests)
scheme.save_as(project.path, 'RoutineWatch', true)
