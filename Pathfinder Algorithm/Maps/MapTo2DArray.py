from PIL import Image
import numpy as np

def closest_colour(rgb, colour_map, tolerance=10):
    for colour, value in colour_map.items():
        if all(abs(int(c1) - int(c2)) <= tolerance for c1, c2 in zip(rgb, colour)):
            return value
    return -1


image = Image.open(r"C:\Users\isaac\OneDrive\Desktop\NEA Project new\NEA-Project-2\Pathfinder Algorithm\Maps\MapOfEuropeNonNamed.png")
imageArray = np.array(image)

colourMap = {
    (0,0,0): 0, #black
    (255,255,250): 1, #white
    (163,73,164): 2 #purple (border)   
}

mappedArray = np.zeros((imageArray.shape[0], imageArray.shape[1]), dtype=int)
print("processing")
for i in range(imageArray.shape[0]):
    for j in range(imageArray.shape[1]):
        rgb = tuple(imageArray[i, j])
        mappedArray[i, j] = closest_colour(rgb, colourMap)
print("running")
np.save(r"C:\Users\isaac\OneDrive\Desktop\NEA Project new\NEA-Project-2\Pathfinder Algorithm\Maps", mappedArray)