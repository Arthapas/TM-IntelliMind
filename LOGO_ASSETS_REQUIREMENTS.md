# Logo Assets Requirements for TM IntelliMind

## Current Issues with Existing Logo
The current `tm-group-logo.png` has readability issues when scaled down due to the text "INSURANCE GROUP" becoming too small. This document outlines the required logo variations to fix these UI/UX issues.

## Required Logo Variations

### 1. Icon-Only Version
**Filename**: `tm-icon-only.png` (and `tm-icon-only.svg`)
**Purpose**: For very small spaces where text is unreadable
**Specifications**:
- Extract only the circular blue/gold symbol from the current logo
- Minimum size: 24x24px should be clearly visible
- Recommended sizes: 32x32, 48x48, 64x64, 128x128px
- Format: PNG with transparency, SVG preferred
- Usage: Navbar on mobile, favicon, very small contexts

### 2. Horizontal Layout Version
**Filename**: `tm-horizontal-logo.png` (and `tm-horizontal-logo.svg`)
**Purpose**: For medium-width spaces where vertical layout is too tall
**Specifications**:
- Symbol on left, "TOKIO MARINE" text on right
- Remove or make "INSURANCE GROUP" smaller/secondary
- Aspect ratio: approximately 3:1 or 4:1 (wide)
- Usage: Medium-width headers, tablet layouts

### 3. TM IntelliMind Branded Version
**Filename**: `tm-intellimind-logo.png` (and `tm-intellimind-logo.svg`)
**Purpose**: Application-specific branding
**Specifications**:
- TM symbol + "IntelliMind" text
- Maintain TM brand colors (blue/gold)
- Consider adding subtle AI/intelligence visual elements
- Usage: Hero sections, about pages, app-specific contexts

### 4. Optimized Current Logo
**Filename**: `tm-group-logo-optimized.png` (and `tm-group-logo.svg`)
**Purpose**: Optimized version of current logo
**Specifications**:
- Same design as current but optimized for web
- SVG format for scalability
- Proper text sizing for smaller displays
- WebP format for better compression

## Implementation Status

### ✅ Completed
- CSS improvements for aspect ratio preservation
- Responsive scaling with clamp()
- Better accessibility with improved alt text
- Logo hover effects and transitions

### 🔄 In Progress
- Logo asset creation requirements documentation
- CSS structure for multiple logo versions

### ⏳ Pending
- Actual logo asset creation (requires designer/image editing)
- Implementation of context-appropriate logo switching
- Performance optimizations with WebP/SVG formats

## CSS Classes Ready for Implementation

```css
/* Already implemented in base.html */
.navbar-brand-logo    /* Main navbar logo */
.logo-hero           /* Hero section logo */
.logo-footer         /* Footer logo */
.logo-icon-only      /* Icon-only version (ready for implementation) */
```

## HTML Structure Ready for Logo Variants

The templates are prepared to use different logo versions based on context:

```html
<!-- For mobile navbar - icon only -->
<img src="{% static 'images/logos/tm-icon-only.svg' %}" 
     alt="TM IntelliMind" 
     class="logo-icon-only">

<!-- For desktop navbar - horizontal layout -->
<img src="{% static 'images/logos/tm-horizontal-logo.svg' %}" 
     alt="TM IntelliMind - Tokio Marine" 
     class="navbar-brand-logo">

<!-- For hero section - branded version -->
<img src="{% static 'images/logos/tm-intellimind-logo.svg' %}" 
     alt="TM IntelliMind - AI-Powered Meeting Intelligence" 
     class="logo-hero">
```

## Next Steps

1. **Create Logo Assets**: Use image editing software to create the required variations
2. **Implement Responsive Logo Switching**: Use CSS media queries to show appropriate logo versions
3. **Add WebP Support**: Implement fallback for browsers that don't support WebP
4. **Performance Testing**: Ensure logo loading doesn't impact page performance

## Design Guidelines

- Maintain consistent TM brand colors (blue gradient, gold accents)
- Ensure minimum contrast ratios for accessibility (4.5:1 for normal text)
- Test readability at smallest intended sizes
- Consider dark mode variations if needed
- Optimize for various screen densities (1x, 2x, 3x)