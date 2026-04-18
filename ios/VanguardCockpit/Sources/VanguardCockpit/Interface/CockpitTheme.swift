import SwiftUI

/// Design tokens aligned with web `index.css` (charcoal shell + industrial amber accents).
enum CockpitTheme {
    static let charcoal1000 = Color(red: 0.055, green: 0.063, blue: 0.075)
    static let charcoal950 = Color(red: 0.071, green: 0.082, blue: 0.102)
    static let charcoal900 = Color(red: 0.102, green: 0.118, blue: 0.141)
    static let charcoal850 = Color(red: 0.133, green: 0.149, blue: 0.180)

    static let mist = Color(red: 0.847, green: 0.871, blue: 0.910)
    static let mistMuted = Color(red: 0.604, green: 0.639, blue: 0.690)

    static let industrialAmber = Color(red: 0.910, green: 0.580, blue: 0.110)
    static let industrialAmberDim = Color(red: 0.722, green: 0.451, blue: 0.071)

    static let divider = Color.white.opacity(0.075)
    static let annunciatorOnFill = industrialAmber.opacity(0.18)
    static let annunciatorOnBorder = industrialAmber.opacity(0.55)
    static let annunciatorOffFill = Color.white.opacity(0.04)
    static let annunciatorOffBorder = Color.white.opacity(0.12)

    /// Secondary chart series (muted, not competing with amber accents).
    static let chartSeriesPrimary = Color(red: 0.35, green: 0.55, blue: 0.58)
    static let chartSeriesSecondary = Color(red: 0.40, green: 0.48, blue: 0.42).opacity(0.75)
    static let chartDeep = Color(red: 0.32, green: 0.52, blue: 0.40)
    static let chartMixed = industrialAmberDim.opacity(0.85)
    static let chartShallow = Color(red: 0.62, green: 0.38, blue: 0.22)
}

extension View {
    func cockpitRootBackground() -> some View {
        background(
            ZStack {
                CockpitTheme.charcoal1000
                RadialGradient(
                    colors: [CockpitTheme.charcoal900.opacity(0.9), CockpitTheme.charcoal1000],
                    center: .top,
                    startRadius: 40,
                    endRadius: 520
                )
            }
            .ignoresSafeArea()
        )
    }

    func cockpitKickerStyle() -> some View {
        font(.caption2)
            .fontWeight(.semibold)
            .textCase(.uppercase)
            .tracking(0.7)
            .foregroundStyle(CockpitTheme.mistMuted)
    }

    func cockpitBodySecondary() -> some View {
        font(.caption)
            .foregroundStyle(CockpitTheme.mistMuted)
    }

    func cockpitPrimaryButtonStyle() -> some View {
        buttonStyle(CockpitPrimaryButtonStyle())
    }
}

struct CockpitPrimaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(CockpitTheme.charcoal1000)
            .padding(.horizontal, 14)
            .padding(.vertical, 8)
            .background(CockpitTheme.industrialAmber.opacity(configuration.isPressed ? 0.75 : 1))
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

struct CockpitSecondaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.caption.weight(.medium))
            .foregroundStyle(CockpitTheme.mist)
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(CockpitTheme.charcoal850.opacity(configuration.isPressed ? 0.9 : 0.65))
            .overlay(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .stroke(CockpitTheme.divider, lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}
