#!/usr/bin/env python3
import cv2
import os
import numpy as np

# --- Configuration ---
IMAGE_FILENAME = "01_source_pngs/page-001.png"
OUTPUT_DIR = "poc_output"
# Corrected: Define base filenames here
GRAYSCALE_BASE_FILENAME = "grayscale_page-001" 
BINARIZED_BASE_FILENAME = "binarized_page-001" 
PROCESSED_LINES_BASE_FILENAME = "processed_lines_page-001"
TABLE_BBOX_BASE_FILENAME = "table_bbox_page-001" # This will be the cell grid image

# Best parameters from sweep, now tuning v_line_tolerance
HOUGH_MIN_LINE_LENGTH = 75
HOUGH_THRESHOLD = 100
HOUGH_MAX_LINE_GAP = 20
H_LINE_MERGE_TOLERANCE = 15
V_LINE_MERGE_TOLERANCE_TO_TEST = 5 # New value to test (was 7)


def process_detected_lines(lines, is_horizontal, tolerance=10):
    # (This function remains unchanged from the previous version)
    if not lines: return []
    representative_coords = []
    if is_horizontal:
        coords_with_orig = [((line[1] + line[3]) // 2, line) for line in lines]
        coords_with_orig.sort(key=lambda item: item[0])
    else:
        coords_with_orig = [((line[0] + line[2]) // 2, line) for line in lines]
        coords_with_orig.sort(key=lambda item: item[0])
    if not coords_with_orig: return []
    merged_coords = [coords_with_orig[0][0]] 
    for current_coord, _ in coords_with_orig[1:]:
        if abs(current_coord - merged_coords[-1]) > tolerance:
            merged_coords.append(current_coord)
    return sorted(list(set(merged_coords)))

def detect_and_process_lines(binarized_image_path, original_image_path_for_drawing, 
                             hough_min_line_length, 
                             h_line_tolerance, v_line_tolerance,
                             output_suffix=""): 
    bin_img = cv2.imread(binarized_image_path, cv2.IMREAD_GRAYSCALE)
    if bin_img is None: print(f"Error: Could not load binarized image from {binarized_image_path}"); return [], [], None
    
    img_for_drawing_lines = cv2.imread(original_image_path_for_drawing) 
    if img_for_drawing_lines is None:
        print(f"Error: Could not load original image for drawing lines from {original_image_path_for_drawing}")
        img_for_drawing_lines = cv2.cvtColor(bin_img, cv2.COLOR_GRAY2BGR)

    rho = 1; theta = np.pi / 180
    
    print(f"\n--- Running HoughLinesP with MLL={hough_min_line_length}, Thr={HOUGH_THRESHOLD}, MaxGap={HOUGH_MAX_LINE_GAP} ---")
    raw_lines = cv2.HoughLinesP(bin_img, rho, theta, HOUGH_THRESHOLD, None, 
                                hough_min_line_length, HOUGH_MAX_LINE_GAP)
    
    raw_horizontal_segments = []; raw_vertical_segments = []

    if raw_lines is not None:
        for i in range(0, len(raw_lines)):
            l = raw_lines[i][0]; x1, y1, x2, y2 = l
            angle = np.arctan2(y2 - y1, x2 - x1) * 180. / np.pi; line_len = np.sqrt((x2-x1)**2 + (y2-y1)**2)
            if abs(angle) < 5 and line_len > 200: 
                raw_horizontal_segments.append(l)
            elif abs(abs(angle) - 90) < 5: 
                raw_vertical_segments.append(l)
        
        processed_h_coords = process_detected_lines(raw_horizontal_segments, is_horizontal=True, tolerance=h_line_tolerance)
        processed_v_coords = process_detected_lines(raw_vertical_segments, is_horizontal=False, tolerance=v_line_tolerance)
        
        print(f"Raw classified: {len(raw_horizontal_segments)} H, {len(raw_vertical_segments)} V") # Moved print for context
        print(f"Processed to {len(processed_h_coords)} unique H-lines (tolerance={h_line_tolerance}).")
        print(f"Processed to {len(processed_v_coords)} unique V-lines (tolerance={v_line_tolerance}).")

        img_for_processed_lines_display = img_for_drawing_lines.copy()
        page_height, page_width = bin_img.shape[:2]
        for y_coord in processed_h_coords:
            cv2.line(img_for_processed_lines_display, (0, y_coord), (page_width, y_coord), (0, 255, 255), 2) 
        for x_coord in processed_v_coords:
            cv2.line(img_for_processed_lines_display, (x_coord, 0), (x_coord, page_height), (255, 0, 255), 2) 
        
        processed_lines_output_path = os.path.join(OUTPUT_DIR, f"{PROCESSED_LINES_BASE_FILENAME}_MLL{hough_min_line_length}_VTOL{v_line_tolerance}{output_suffix}.png")
        cv2.imwrite(processed_lines_output_path, img_for_processed_lines_display)
        print(f"Saved image with processed lines to: {processed_lines_output_path}")
        
        return processed_h_coords, processed_v_coords, img_for_drawing_lines.shape
    else:
        print(f"No raw lines were detected (minLineLength={hough_min_line_length}).")
        return [], [], None

def process_image_initial(image_path):
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR); print(f"Created directory: {OUTPUT_DIR}")
    img = cv2.imread(image_path)
    if img is None: print(f"Error: Could not load image from {image_path}"); return None
    
    gray_path = os.path.join(OUTPUT_DIR, GRAYSCALE_BASE_FILENAME + ".png") # Uses global
    bin_path = os.path.join(OUTPUT_DIR, BINARIZED_BASE_FILENAME + ".png")   # Uses global

    gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if not os.path.exists(gray_path): 
        cv2.imwrite(gray_path, gray_img)
        print(f"Saved grayscale image to: {gray_path}")
    
    binarized_img = cv2.adaptiveThreshold(gray_img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
    if not os.path.exists(bin_path): 
        cv2.imwrite(bin_path, binarized_img)
        print(f"Saved binarized image to: {bin_path}")
    return bin_path

def define_table_grid_and_draw_cells(processed_h_coords, processed_v_coords, original_image_path, hough_mll, v_tol, output_suffix=""):
    # Renamed function for clarity, was define_table_bounding_box
    img_for_cells = cv2.imread(original_image_path)
    if img_for_cells is None: print(f"Error loading image for drawing cells: {original_image_path}"); return []

    # Filename now explicitly for cells, even if it was used for bbox before
    cell_grid_output_path = os.path.join(OUTPUT_DIR, f"{TABLE_BBOX_BASE_FILENAME}_MLL{hough_mll}_VTOL{v_tol}{output_suffix}.png")

    if not processed_h_coords or len(processed_h_coords) < 2 or \
       not processed_v_coords or len(processed_v_coords) < 2:
        print("Not enough H or V lines to define cells.")
        page_height, page_width = img_for_cells.shape[:2]
        for y_coord in processed_h_coords: cv2.line(img_for_cells, (0, y_coord), (page_width, y_coord), (0, 255, 255), 1) 
        for x_coord in processed_v_coords: cv2.line(img_for_cells, (x_coord, 0), (x_coord, page_height), (255, 0, 255), 1)
        cv2.imwrite(cell_grid_output_path, img_for_cells) 
        print(f"Saved image (lines, no cells drawn) to: {cell_grid_output_path}")
        return []
        
    print(f"Drawing cells based on {len(processed_h_coords)-1} rows and {len(processed_v_coords)-1} columns.")
    cell_coordinates = []
    for i in range(len(processed_h_coords) - 1):
        y_start = processed_h_coords[i]
        y_end = processed_h_coords[i+1]
        for j in range(len(processed_v_coords) - 1):
            x_start = processed_v_coords[j]
            x_end = processed_v_coords[j+1]
            # Ensure x_start < x_end and y_start < y_end for valid rectangles
            if x_start < x_end and y_start < y_end:
                cv2.rectangle(img_for_cells, (x_start, y_start), (x_end, y_end), (0,0,255), 1) 
                cell_coordinates.append((x_start, y_start, x_end, y_end))
    
    cv2.imwrite(cell_grid_output_path, img_for_cells)
    print(f"Saved image with cell grid to: {cell_grid_output_path}")
    return cell_coordinates

if __name__ == "__main__":
    if not os.path.exists(IMAGE_FILENAME):
        print(f"Error: Input image not found at {IMAGE_FILENAME}")
    else:
        print("Ensuring initial image processing (grayscale and binarization)...")
        binarized_image_filepath = process_image_initial(IMAGE_FILENAME)
        if binarized_image_filepath is None:
            print("Exiting due to error in initial image processing.")
            exit()
        print(f"Using binarized image: {binarized_image_filepath}")

        mll_to_use = HOUGH_MIN_LINE_LENGTH 
        v_tol_to_use = V_LINE_MERGE_TOLERANCE_TO_TEST 

        h_coords, v_coords, shape = detect_and_process_lines(
            binarized_image_filepath, 
            IMAGE_FILENAME,
            hough_min_line_length=mll_to_use,
            h_line_tolerance=H_LINE_MERGE_TOLERANCE, 
            v_line_tolerance=v_tol_to_use,
            output_suffix=f"_MLL{mll_to_use}_VTOL{v_tol_to_use}"
        )
        
        if h_coords and v_coords and shape:
            print(f"For MLL={mll_to_use}, VTOL={v_tol_to_use}: Proceeding to define cells with {len(h_coords)} H-lines and {len(v_coords)} V-lines.")
            cells = define_table_grid_and_draw_cells(
                h_coords, v_coords, IMAGE_FILENAME, 
                hough_mll=mll_to_use, v_tol=v_tol_to_use,
                output_suffix="" # Suffix already handled by processed_lines/cell_grid path construction
            )
            if cells:
                print(f"For MLL={mll_to_use}, VTOL={v_tol_to_use}: Identified {len(cells)} cell coordinates.")
        else:
            print(f"For MLL={mll_to_use}, VTOL={v_tol_to_use}: Could not proceed to define cells due to missing line data or image shape.")
        print("-" * 40)
