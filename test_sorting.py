#!/usr/bin/env python3

def get_image_sort_key(image_info):
    """Get sort key for proper image ordering"""
    filename = image_info['filename'].lower()
    
    # Main/Primary images first
    if 'main' in filename or 'primary' in filename:
        return (0, filename)
    
    # Then numbered images in order
    if '2nd' in filename:
        return (1, filename)
    elif '3rd' in filename:
        return (2, filename)
    elif '4th' in filename:
        return (3, filename)
    elif '5th' in filename:
        return (4, filename)
    elif '6th' in filename:
        return (5, filename)
    elif '7th' in filename:
        return (6, filename)
    elif '8th' in filename:
        return (7, filename)
    else:
        # For images without specific numbering, treat as main image (first)
        return (0, filename)

# Test with Aneros Prelude Enema Bulb images
test_images = [
    {'filename': 'Aneros_Prelude-Enema_Bulb_3rd_Image.jpeg'},
    {'filename': 'Aneros_Prelude_Enema_Bulb.jpeg'},
    {'filename': 'Aneros_Prelude_Enema_Bulb_2nd_Image.jpeg'}
]

print("BEFORE SORTING:")
for i, img in enumerate(test_images):
    print(f"{i+1}. {img['filename']}")

print("\nSORT KEYS:")
for img in test_images:
    key = get_image_sort_key(img)
    print(f"{img['filename']} -> {key}")

test_images.sort(key=get_image_sort_key)

print("\nAFTER SORTING:")
for i, img in enumerate(test_images):
    print(f"{i+1}. {img['filename']}")

# Test with lubricant images
print("\n" + "="*50)
print("LUBRICANT TEST:")

lube_images = [
    {'filename': '810124861551_Main_Photo.jpeg'},
    {'filename': '810124861551_3rd_Photo.jpeg'},
    {'filename': '810124861551_2nd_Photo.jpeg'}
]

print("\nBEFORE SORTING:")
for i, img in enumerate(lube_images):
    print(f"{i+1}. {img['filename']}")

print("\nSORT KEYS:")
for img in lube_images:
    key = get_image_sort_key(img)
    print(f"{img['filename']} -> {key}")

lube_images.sort(key=get_image_sort_key)

print("\nAFTER SORTING:")
for i, img in enumerate(lube_images):
    print(f"{i+1}. {img['filename']}")