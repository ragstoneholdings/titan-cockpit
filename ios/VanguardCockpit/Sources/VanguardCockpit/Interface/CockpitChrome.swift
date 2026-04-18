import UIKit
import SwiftUI

enum CockpitChrome {
    static func configure() {
        let amber = UIColor(CockpitTheme.industrialAmber)
        let mist = UIColor(CockpitTheme.mist)
        let mistMuted = UIColor(CockpitTheme.mistMuted)
        let barBg = UIColor(CockpitTheme.charcoal950)

        let tab = UITabBarAppearance()
        tab.configureWithOpaqueBackground()
        tab.backgroundColor = barBg
        tab.shadowColor = .clear
        tab.stackedLayoutAppearance.normal.iconColor = mistMuted
        tab.stackedLayoutAppearance.normal.titleTextAttributes = [.foregroundColor: mistMuted]
        tab.stackedLayoutAppearance.selected.iconColor = amber
        tab.stackedLayoutAppearance.selected.titleTextAttributes = [.foregroundColor: amber]

        UITabBar.appearance().standardAppearance = tab
        UITabBar.appearance().scrollEdgeAppearance = tab
        UITabBar.appearance().tintColor = amber
        UITabBar.appearance().unselectedItemTintColor = mistMuted

        let nav = UINavigationBarAppearance()
        nav.configureWithOpaqueBackground()
        nav.backgroundColor = barBg
        nav.titleTextAttributes = [.foregroundColor: UIColor(CockpitTheme.mist)]
        nav.largeTitleTextAttributes = [.foregroundColor: UIColor(CockpitTheme.mist)]
        nav.shadowColor = .clear

        UINavigationBar.appearance().standardAppearance = nav
        UINavigationBar.appearance().compactAppearance = nav
        UINavigationBar.appearance().scrollEdgeAppearance = nav
        UINavigationBar.appearance().tintColor = amber
    }
}
