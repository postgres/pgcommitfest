// An input validator for the color picker. Points out low-contrast tag color
// choices.
const input = document.getElementById("id_color");
input.addEventListener("input", (event) => {
	// Don't do anything if the color code doesn't pass default validity.
	input.setCustomValidity("");
	if (!input.validity.valid) {
		return;
	}

	// Break the #rrggbb color code into RGB components.
	color = parseInt(input.value.substr(1), 16);
	red = ((color & 0xFF0000) >> 16) / 255.;
	green = ((color & 0x00FF00) >> 8) / 255.;
	blue = (color & 0x0000FF) / 255.;

	// Compare the contrast ratio against white. All the magic math comes from
	// Web Content Accessibility Guidelines (WCAG) 2.2, Technique G18:
	//
	//     https://www.w3.org/WAI/WCAG22/Techniques/general/G18.html
	//
	function l(val) {
		if (val <= 0.04045) {
			return val / 12.92;
		}
		return ((val + 0.055) / 1.055) ** 2.4;
	}

	lum = 0.2126 * l(red) + 0.7152 * l(green) + 0.0722 * l(blue);
	contrast = (1 + 0.05) / (lum + 0.05);

	// Complain if we're below WCAG 2.2 recommendations.
	if (contrast < 4.5) {
		input.setCustomValidity(
			"Consider choosing a darker color. "
			+ "(Tag text is small and white.)\n\n"
		    + "Contrast ratio: " + (Math.trunc(contrast * 10) / 10) + " (< 4.5)"
		);

		// The admin form uses novalidate, so manually display the browser's
		// validity popup. (The user can still ignore it if desired.)
		input.reportValidity();
	}
});
