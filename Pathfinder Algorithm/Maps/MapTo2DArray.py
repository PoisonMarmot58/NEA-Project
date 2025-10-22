from PIL import Image
import numpy as np

image = Image.open("C/Users/isaac/OneDrive/Desktop/NEA Project new/NEA-Project-2/Pathfinder Algorithm/Maps/MapOfEuropeNonNamed.png")

imageArray = np.array(image)

colourMap = {
    (0,0,0): 0, #black
    (255,255,250): 1, #white
    (163,73,164): 2 #purple (border)   
}

mappedArray = np.zeros((imageArray.shape[0], imageArray.shape[1]), dtype=int)

for i in range(imageArray.shape[0]):
    for j in range(imageArray.shape[1]):
        rgb = tuple(imageArray[i, j])
        mappedArray[i, j] = colourMap.get(rgb, -1)

print(colourMap)