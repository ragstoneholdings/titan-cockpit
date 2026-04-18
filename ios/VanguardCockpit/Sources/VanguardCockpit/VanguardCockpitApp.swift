import SwiftUI
import SwiftData

@main
struct VanguardCockpitApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate

    init() {
        CockpitChrome.configure()
    }

    var sharedModelContainer: ModelContainer = {
        let schema = Schema([SovereigntySnapshot.self])
        let config = ModelConfiguration(schema: schema, isStoredInMemoryOnly: false)
        return try! ModelContainer(for: schema, configurations: [config])
    }()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .preferredColorScheme(.dark)
                .cockpitRootBackground()
        }
        .modelContainer(sharedModelContainer)
    }
}
